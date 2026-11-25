#!/usr/bin/env python3
"""MCP server para GNS3 2.2 (API REST v2) — local, sin secretos en el prompt.

Credenciales y rutas salen de ~/.config/GNS3/2.2/gns3_server.conf
(override por env: GNS3_URL, GNS3_USER, GNS3_PASSWORD).

Transporte: stdio. Uso: gns3-mcp  (o python -m gns3_mcp_server)
"""
from __future__ import annotations

import asyncio
import base64
import configparser
import fnmatch
import html
import json
import os
import re
import shutil
import subprocess
import time
import unicodedata
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
import websockets
from fastmcp import FastMCP

import gns3core as core

CONF = Path(os.path.expanduser("~/.config/GNS3/2.2/gns3_server.conf"))

mcp = FastMCP("gns3")


# ────────────────────────────── configuración ──────────────────────────────
def _conf() -> dict[str, str]:
    cfg = configparser.ConfigParser()
    data = {"host": "127.0.0.1", "port": "3080", "user": "admin", "password": ""}
    if CONF.exists():
        cfg.read(CONF)
        sec = cfg["Server"] if cfg.has_section("Server") else {}
        for k in ("host", "port", "user", "password"):
            if sec.get(k):
                data[k] = sec[k]
        data["images_path"] = sec.get("images_path", "")
        data["projects_path"] = sec.get("projects_path", "")
        data["appliances_path"] = sec.get("appliances_path", "")
        data["configs_path"] = sec.get("configs_path", "")
        data["ubridge_path"] = sec.get("ubridge_path", "")
    host = data["host"]
    if host in ("localhost", "0.0.0.0"):
        host = "127.0.0.1"
    data["url"] = os.environ.get("GNS3_URL", f"http://{host}:{data['port']}")
    data["user"] = os.environ.get("GNS3_USER", data["user"])
    data["password"] = os.environ.get("GNS3_PASSWORD", data["password"])
    return data


def _api(method: str, path: str, body: Any = None, timeout: float = 60.0, raw: bool = False):
    c = _conf()
    url = c["url"] + path
    try:
        r = httpx.request(
            method,
            url,
            json=body,
            auth=(c["user"], c["password"]),
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )
    except httpx.HTTPError as e:
        return {"error": "no se pudo conectar con el servidor GNS3", "url": url, "detail": str(e)}
    if r.status_code >= 400:
        return {"error": f"HTTP {r.status_code}", "path": path, "detail": r.text[:1500]}
    if raw:
        return r.content
    if not r.content:
        return None
    try:
        return r.json()
    except json.JSONDecodeError:
        return {"body": r.text[:2000]}


def _server_up() -> tuple[bool, Any]:
    info = _api("GET", "/v2/version", timeout=5)
    if isinstance(info, dict) and info.get("error"):
        return False, info
    return True, info


def _err_msg(status: int, body: Any, what: str) -> dict:
    """Error de la API con el mensaje interno, no con el volcado de schema anidado."""
    msg = body.get("message") if isinstance(body, dict) else body
    if isinstance(msg, str) and "JSON schema error" in msg:
        tail = re.search(r"\}'\s*:\s*(.+)$", msg, re.S)
        if tail:
            msg = tail.group(1)
        else:
            m = re.search(r'"message"\s*:\s*"([^"]+)"', msg[msg.find("{"):])
            if m:
                msg = m.group(1)
            else:
                m = re.search(r"['\"]([^'\"]+)['\"]\]", msg[msg.find("{"):])
                if m:
                    msg = m.group(1)
    if msg is None:
        msg = "sin detalle"
    return {"error": f"{what} falló: [{status}] {str(msg)[:400]}"}


def _api_error(status: int, body: Any, what: str) -> dict:
    """Error de compute con status explícito y sin sustituir su mensaje por contenido inventado."""
    msg = body.get("message") if isinstance(body, dict) else body
    if isinstance(msg, bytes):
        msg = msg.decode(errors="replace")
    return {"error": f"{what} falló: [{status}] {str(msg)[:4000] if msg is not None else 'sin detalle'}",
            "status": status}


def _unexpected_keys(body: Any) -> list[str]:
    """Claves que el schema de la API rechazó (`Additional properties ... were unexpected`)."""
    msg = body.get("message") if isinstance(body, dict) else body
    if not isinstance(msg, str):
        return []
    m = re.search(r"\(([^)]*)\) were unexpected", msg)
    return re.findall(r"'([^']+)'", m.group(1)) if m else []


def _verified_list(client, path: str, items: list[dict], what: str) -> tuple[list[dict], Optional[dict]]:
    """Distinguue una lista vacía real de un fallo que el wrapper del núcleo convirtió en []."""
    if items:
        return items, None
    try:
        st, body = client.get(path)
    except ConnectionError as e:
        return [], {"error": str(e)}
    if st == 200 and isinstance(body, list):
        return body, None
    return [], _err_msg(st, body, what)


# ────────────────────────────── helpers ──────────────────────────────
def _projects() -> list[dict]:
    return _api("GET", "/v2/projects") or []


def _resolve_project(project_id: Optional[str], name: Optional[str] = None) -> tuple[Optional[str], Optional[dict]]:
    projs = _projects()
    if not isinstance(projs, list):
        return None, None
    if project_id:
        return project_id, next((p for p in projs if p["project_id"] == project_id), None)
    if name:
        for p in projs:
            if p["name"].lower() == name.lower():
                return p["project_id"], p
        return None, None
    opened = [p for p in projs if p.get("status") == "opened"]
    if len(opened) == 1:
        return opened[0]["project_id"], opened[0]
    if len(projs) == 1:
        return projs[0]["project_id"], projs[0]
    return None, None


def _nodes(project_id: str) -> list[dict]:
    res = _api("GET", f"/v2/projects/{project_id}/nodes")
    return res if isinstance(res, list) else []


def _ensure_open(project_id: str) -> Optional[dict]:
    """Abre el proyecto si está cerrado (GNS3 responde 403 'project is not opened' si no)."""
    info = _api("GET", f"/v2/projects/{project_id}")
    if not isinstance(info, dict) or info.get("error"):
        return info if isinstance(info, dict) else None
    if info.get("status") in ("opened", "closed", None):
        if info.get("status") == "opened":
            return None
        res = _api("POST", f"/v2/projects/{project_id}/open", timeout=300)
        if isinstance(res, dict) and res.get("error"):
            return res
        return None
    return None


def _match_nodes(nodes: list[dict], pattern: Optional[str]) -> list[dict]:
    if not pattern:
        return []
    if pattern in ("*", "all"):
        return nodes
    if "," in pattern or pattern.strip().startswith("["):
        pats = [p.strip() for p in pattern.strip("[]").replace(",", " ").split()] or [pattern]
    else:
        pats = [pattern]
    out = []
    for n in nodes:
        for pat in pats:
            if n["name"].lower() == pat.lower() or fnmatch.fnmatch(n["name"].lower(), pat.lower()):
                out.append(n)
                break
        else:
            if n.get("node_id") == pattern:
                out.append(n)
    return out


def _node_summary(n: dict) -> dict:
    return {
        "name": n.get("name"),
        "node_id": n.get("node_id"),
        "type": n.get("node_type"),
        "status": n.get("status"),
        "console": n.get("console"),
        "ports": [p.get("name") for p in (n.get("ports") or [])],
    }


def _resolve_template(client, template_id: Optional[str] = None,
                      name: Optional[str] = None) -> tuple[Optional[dict], Optional[dict]]:
    """Plantilla por id (admite prefijo) o nombre (exacto, luego parcial único)."""
    tpls = client.templates()
    names = [t.get("name") for t in tpls]
    if not tpls:
        return None, {"error": "el servidor no tiene plantillas"}
    if template_id:
        hit = next((t for t in tpls if t["template_id"] == template_id), None) or next(
            (t for t in tpls if str(t["template_id"]).startswith(template_id)), None)
        if hit:
            return hit, None
        return None, {"error": f"plantilla no encontrada: {template_id}", "available": names}
    if not name:
        return None, {"error": "indica name o template_id"}
    low = name.lower()
    hits = [t for t in tpls if str(t.get("name", "")).lower() == low]
    if not hits:
        hits = [t for t in tpls if low in str(t.get("name", "")).lower()
                or str(t.get("template_id", "")).startswith(name)]
    if len(hits) == 1:
        return hits[0], None
    if not hits:
        return None, {"error": f"plantilla no encontrada: {name}", "available": names}
    return None, {"error": f"'{name}' es ambiguo", "candidates": [t.get("name") for t in hits]}


def _endpoint_error(node: dict, adapter: int, port: int, side: str = "") -> Optional[dict]:
    """Explica un extremo imposible antes de que GNS3 devuelva un 404 opaco."""
    name, ntype = node.get("name"), node.get("node_type")
    ports = node.get("ports") or []
    prefix = f"{side}_" if side else ""
    if ntype == "ethernet_switch":
        max_port = max((p.get("port_number", 0) for p in ports), default=7)
        if adapter != 0:
            return {"error": f"{name} es un ethernet_switch: sus {max_port + 1} puertos viven todos "
                             f"en el adapter 0. Con {prefix}adapter={adapter}, {prefix}port={port} GNS3 "
                             f"respondería 'Port {adapter}/{port} for {name} not found'. Usa "
                             f"{prefix}adapter=0 y {prefix}port=N (0-{max_port})."}
        if not 0 <= port <= max_port:
            return {"error": f"{name} no tiene el puerto {port} en el adapter 0 (rango 0-{max_port})",
                    "ports": [f"0/{p.get('port_number')}" for p in ports]
                    or [f"0/{i}" for i in range(max_port + 1)]}
        return None
    if ports:
        valid = {(p.get("adapter_number", 0), p.get("port_number", 0)) for p in ports}
        if (adapter, port) not in valid:
            return {"error": f"{name} no tiene el puerto {adapter}/{port}",
                    "ports": [f"{a}/{p}" for a, p in sorted(valid)]}
    return None


# ────────────────────────────── tools ──────────────────────────────
@mcp.tool
def gns3_status() -> dict:
    """Estado del servidor GNS3 local: versión, computes y proyecto abierto."""
    up, info = _server_up()
    if not up:
        return {"running": False, "detail": info}
    compute_error = None
    try:
        computes = _client().computes()
    except ConnectionError as e:
        computes = []
        compute_error = str(e)
    projs = _projects()
    opened = [p["name"] for p in projs if p.get("status") == "opened"] if isinstance(projs, list) else []
    c = _conf()
    try:
        st_v1, version_v1 = _client().v1_version()
    except ConnectionError as e:
        version_v1 = {"error": str(e)}
    else:
        if st_v1 != 200:
            version_v1 = _api_error(st_v1, version_v1, "obtener versión v1")
    return {
        "running": True,
        "version": info.get("version") if isinstance(info, dict) else info,
        "version_v1": version_v1,
        "url": c["url"],
        "local": info.get("local") if isinstance(info, dict) else None,
        "computes": [{"id": x.get("compute_id"), "name": x.get("name"), "connected": x.get("connected")} for x in computes],
        "projects": len(projs) if isinstance(projs, list) else 0,
        "opened_projects": opened,
        "paths": {k: c.get(k) for k in ("images_path", "projects_path", "appliances_path", "configs_path", "ubridge_path")},
        **({"error": compute_error} if compute_error else {}),
    }


@mcp.tool
def gns3_projects(action: str = "list", name: Optional[str] = None, project_id: Optional[str] = None,
                  project_name: Optional[str] = None, new_name: Optional[str] = None) -> Any:
    """Proyectos: action=list|create|open|close|update|delete|info.

    Identifica por project_id, name o project_name. `update` renombra con `new_name`.
    """
    action = action.lower()
    name = name or project_name
    if action == "list":
        projs = _projects()
        return [
            {"name": p["name"], "project_id": p["project_id"], "status": p["status"],
             "path": p.get("path"), "filename": p.get("filename")}
            for p in projs
        ] if isinstance(projs, list) else projs
    client = _client()
    if action == "create":
        if not name:
            return {"error": "name es obligatorio para create"}
        path = os.path.join(_conf().get("projects_path") or os.path.expanduser("~/GNS3/projects"), name)
        try:
            st, res = client.post("/v2/projects", {"name": name, "path": path}, timeout=120)
        except ConnectionError as e:
            return {"error": str(e)}
        return res if st in (200, 201) else _err_msg(st, res, "crear proyecto")
    pid, proj = _resolve_project(project_id, name)
    if not pid:
        return {"error": "proyecto no encontrado", "project_id": project_id, "name": name}
    if action == "open":
        try:
            st, res = client.post(f"/v2/projects/{pid}/open", timeout=180)
        except ConnectionError as e:
            return {"error": str(e)}
        if st not in (200, 201):
            return _err_msg(st, res, "abrir proyecto")
    elif action == "close":
        try:
            st, res = client.project_close(pid)
        except ConnectionError as e:
            return {"error": str(e)}
        if st not in (200, 201):
            return _err_msg(st, res, "cerrar proyecto")
    elif action == "update":
        if not new_name:
            return {"error": "update exige new_name"}
        try:
            st, res = client.put(f"/v2/projects/{pid}", {"name": new_name}, timeout=120)
        except ConnectionError as e:
            return {"error": str(e)}
        if st not in (200, 201):
            return _err_msg(st, res, "actualizar proyecto")
        return {"updated": True, "project_id": pid, "name": (res or {}).get("name", new_name)}
    elif action == "delete":
        try:
            st, res = client.project_delete(pid)
        except ConnectionError as e:
            return {"error": str(e)}
        out = {"deleted": st in (200, 204), "project_id": pid}
        if not out["deleted"]:
            out.update(_err_msg(st, res, "borrar proyecto"))
        return out
    elif action != "info":
        return {"error": f"acción desconocida: {action}"}
    try:
        return client.project_get(pid)
    except (ConnectionError, RuntimeError) as e:
        return {"error": str(e)}


@mcp.tool
def gns3_templates(kind: Optional[str] = None) -> Any:
    """Plantillas del servidor (qemu, docker, vpcs, iou, dynamips...). kind filtra por template_type."""
    tpls = _api("GET", "/v2/templates")
    if not isinstance(tpls, list):
        return tpls
    out = []
    for t in tpls:
        if kind and t.get("template_type") != kind:
            continue
        out.append({
            "name": t.get("name"),
            "template_id": t.get("template_id"),
            "type": t.get("template_type"),
            "image": t.get("hda_disk_image") or t.get("image") or t.get("cdrom_image") or "",
            "adapters": t.get("adapters"),
            "ram": t.get("ram"),
        })
    return out


@mcp.tool
def gns3_template(
    action: str = "list",
    name: Optional[str] = None,
    template_id: Optional[str] = None,
    from_node: Optional[str] = None,
    node_type: Optional[str] = None,
    properties: Optional[dict] = None,
    console: Optional[int] = None,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    x: int = 0,
    y: int = 0,
    new_name: Optional[str] = None,
    filename: Optional[str] = None,
    content: Optional[str] = None,
    confirm: bool = False,
) -> Any:
    """Plantillas del servidor: action=list|create|update|delete|apply|duplicate|base-config.

    list   — nombre, tipo y template_id de cada plantilla.
    create — desde un nodo existente (`from_node`, nombre o id, copia `node_type` y
             `properties`) o desde cero (`node_type` + `properties`). `name` es el nombre
             de la plantilla. Con `console` (puerto VNC) se fija **en la plantilla** y se
             verifica releyéndola: el `PUT` sobre un nodo ignora `console` y devuelve 200.
    update — por `name` o `template_id`; aplica `properties` (claves planas de la
             plantilla) y/o `console`, y verifica los valores releyendo la plantilla.
    delete — por `name` o `template_id`; devuelve `{"deleted": bool}`.
    apply  — instancia la plantilla (`name` o `template_id`) en un proyecto, en (`x`, `y`);
             delega en `gns3_node_edit(action="create", template=...)`.
    duplicate — duplica la plantilla; `new_name` nombra la copia.
    base-config — sin `filename`, lista las configuraciones base disponibles. Con
              `template_id`/`name` y `filename`, lee la configuración; con `content`
              la sobrescribe y exige `confirm=True`.
    """
    action = action.lower()
    client = _client()

    if action == "list":
        tpls = _api("GET", "/v2/templates")
        if not isinstance(tpls, list):
            return tpls
        return [{"name": t.get("name"), "type": t.get("template_type"),
                 "template_id": t.get("template_id")} for t in tpls]

    if action == "create":
        props: dict = {}
        if from_node:
            proj, err = _pid_or_error(client, project_id, project_name)
            if err:
                return err
            try:
                src = client.find_node(proj["project_id"], from_node)
                src = client.node_detail(proj["project_id"], src["node_id"])
            except SystemExit as e:
                return {"error": str(e)}
            node_type = src.get("node_type")
            props = dict(src.get("properties") or {})
            name = name or f"{src['name']}-tpl"
        else:
            if not (node_type and properties):
                return {"error": "create exige from_node, o node_type + properties"}
            props = dict(properties)
            name = name or f"{node_type}-{int(time.time()) % 10000}"
        # 2.2.61 rechaza `properties` anidado y los *_md5sum (los calcula el servidor):
        # el cuerpo de la plantilla va plano, y `console` sólo se puede fijar con un PUT.
        body: dict = {"name": name, "template_type": node_type, "compute_id": "local"}
        body.update({k: v for k, v in props.items() if not k.endswith("_md5sum")})
        for attempt in (1, 2):
            st, res = client.post("/v2/templates", body, timeout=120)
            if st in (200, 201):
                break
            bad = _unexpected_keys(res)
            if attempt == 1 and bad:
                for k in bad:
                    body.pop(k, None)
                continue
            return _err_msg(st, res, "crear plantilla")
        res = res if isinstance(res, dict) else {}
        tid = res.get("template_id")
        out = {"created": True, "name": res.get("name", name), "template_id": tid,
               "type": res.get("template_type", node_type), "console": res.get("console")}
        if console is not None and tid:
            # en el POST no se acepta; el PUT sobre la plantilla sí (sobre el nodo, no)
            st2, put_res = client.put(f"/v2/templates/{tid}", {"console": int(console)},
                                      timeout=60)
            st3, got = client.get(f"/v2/templates/{tid}")
            real = got.get("console") if isinstance(got, dict) else None
            out["console"] = real
            out["console_verified"] = real == int(console)
            if not out["console_verified"]:
                detail = (_err_msg(st2, put_res, "fijar console")["error"] if st2 >= 400
                          else _err_msg(st3, got, "releer plantilla")["error"])
                out["detail"] = (f"la plantilla no conserva console={console} "
                                 f"(quedó {real}): {detail}")
        return out

    if action == "update":
        tpl, err = _resolve_template(client, template_id, name)
        if err:
            return err
        body: dict = {k: v for k, v in (properties or {}).items() if not k.endswith("_md5sum")}
        if console is not None:
            body["console"] = int(console)
        if not body:
            return {"error": "update sin cambios: pasa properties o console"}
        st, res = client.template_update(tpl["template_id"], body)
        if st not in (200, 201):
            return _err_msg(st, res, "actualizar plantilla")
        st2, got = client.template_get(tpl["template_id"])
        if st2 != 200 or not isinstance(got, dict):
            return {"updated": True, "name": tpl.get("name"),
                    "template_id": tpl["template_id"], "applied": body,
                    "detail": _err_msg(st2, got, "releer plantilla")["error"]}
        return {"updated": True, "name": got.get("name", tpl.get("name")),
                "template_id": tpl["template_id"], "applied": body,
                "verified": {k: got.get(k) for k in body}}

    if action == "delete":
        tpl, err = _resolve_template(client, template_id, name)
        if err:
            return err
        try:
            st, res = client.template_delete(tpl["template_id"])
        except ConnectionError as e:
            return {"error": str(e)}
        ok = st in (200, 204)
        out = {"deleted": ok, "name": tpl.get("name"), "template_id": tpl["template_id"]}
        if not ok:
            out.update(_err_msg(st, res, "borrar plantilla"))
        return out

    if action == "apply":
        tpl, err = _resolve_template(client, template_id, name)
        if err:
            return err
        res = gns3_node_edit(action="create", project_id=project_id,
                             project_name=project_name, template=tpl["template_id"],
                             x=x, y=y)
        if isinstance(res, dict) and res.get("error"):
            return res
        return {"template": tpl.get("name"), "template_id": tpl["template_id"], "node": res}

    if action == "duplicate":
        tpl, err = _resolve_template(client, template_id, name)
        if err:
            return err
        try:
            st, res = client.template_duplicate(tpl["template_id"], new_name)
        except ConnectionError as e:
            return {"error": str(e)}
        return res if st in (200, 201) else _err_msg(st, res, "duplicar plantilla")

    if action == "base-config":
        if filename is None:
            try:
                st, res = client.template_base_configs()
            except ConnectionError as e:
                return {"error": str(e)}
            return res if st == 200 else _err_msg(st, res, "listar configuraciones base")
        if content is not None and not confirm:
            return {"error": "sobrescribir una configuración base exige confirm=True"}
        tpl, err = _resolve_template(client, template_id, name)
        if err:
            return err
        try:
            got = client.template_base_config(tpl["template_id"], filename, content)
        except ConnectionError as e:
            return {"error": str(e)}
        if content is None:
            if isinstance(got, dict) and got.get("error"):
                return got
            return {"template": tpl.get("name"), "filename": filename, "content": got}
        st, res = got
        if st not in (200, 201):
            return _err_msg(st, res, "escribir configuración base")
        return {"updated": True, "template": tpl.get("name"), "filename": filename}

    return {"error": f"acción desconocida: {action}",
            "valid": ["list", "create", "update", "delete", "apply", "duplicate", "base-config"]}


@mcp.tool
def gns3_nodes(
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    action: str = "list",
    node: Optional[str] = None,
    template: Optional[str] = None,
    x: int = 0,
    y: int = 0,
) -> Any:
    """Nodos: action=list|add|start|stop|reload|suspend|delete.
    `node` acepta nombre, patrón (*, Router*, R[12]) o node_id; `template` es nombre o template_id."""
    pid, _ = _resolve_project(project_id, project_name)
    if not pid:
        return {"error": "proyecto no encontrado", "project_id": project_id, "project_name": project_name}
    err = _ensure_open(pid)
    if err:
        return {"error": "no se pudo abrir el proyecto", "detail": err}
    action = action.lower()

    if action == "add":
        if not template:
            return {"error": "template es obligatorio para add"}
        tpls = _api("GET", "/v2/templates") or []
        tpl = next((t for t in tpls if t.get("template_id") == template), None) or next(
            (t for t in tpls if str(t.get("name", "")).lower() == template.lower()), None)
        if not tpl:
            return {"error": f"plantilla no encontrada: {template}",
                    "available": [t.get("name") for t in tpls]}
        res = _api("POST", f"/v2/projects/{pid}/templates/{tpl['template_id']}", {"x": x, "y": y})
        return _node_summary(res) if isinstance(res, dict) else res

    nodes = _nodes(pid)
    if not nodes:
        return {"error": "el proyecto no está abierto o no tiene nodos", "project_id": pid}

    if action == "list":
        return [_node_summary(n) for n in nodes]

    targets = _match_nodes(nodes, node)
    if not targets:
        return {"error": f"sin coincidencias para {node!r}", "available": [n["name"] for n in nodes]}

    results = []
    client = _client()
    for t in targets:
        nid = t["node_id"]
        try:
            if action in ("start", "stop", "reload", "suspend"):
                st, res = client.node_action(pid, nid, action)
                request_ok = st in (200, 201)
            elif action == "delete":
                st, res = client.delete(f"/v2/projects/{pid}/nodes/{nid}", timeout=180)
                request_ok = st in (200, 204)
            else:
                return {"error": f"acción desconocida: {action}"}
            time.sleep(0.8)
            state = client.node_detail(pid, nid)
        except ConnectionError as e:
            return {"error": str(e), "results": results}
        except RuntimeError as e:
            state = {"error": str(e)}
        if not request_ok:
            detail = _err_msg(st, res, f"{action} de {t['name']}")["error"]
        else:
            detail = state.get("error") if isinstance(state, dict) else None
        results.append({
            "name": t["name"],
            "request_ok": request_ok,
            "status": state.get("status") if isinstance(state, dict) else None,
            "detail": detail,
        })
    return results


@mcp.tool
def gns3_nodes_bulk(
    action: str,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    confirm: bool = False,
) -> Any:
    """Acción masiva sobre todos los nodos: action=start|stop|suspend|reload.

    Cambia el estado de toda la topología y exige `confirm=True`.
    """
    action = action.lower()
    if action not in ("start", "stop", "suspend", "reload"):
        return {"error": f"acción masiva desconocida: {action}",
                "valid": ["start", "stop", "suspend", "reload"]}
    if not confirm:
        return {"error": f"acción masiva {action} exige confirm=True"}
    client = _client()
    proj, err = _pid_or_error(client, project_id, project_name)
    if err:
        return err
    try:
        st, res = client.nodes_action(proj["project_id"], action)
    except ConnectionError as e:
        return {"error": str(e)}
    if st not in (200, 201, 204):
        return _api_error(st, res, f"acción masiva {action}")
    return res if res is not None else {"ok": True}


@mcp.tool
def gns3_links(
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    action: str = "list",
    link_id: Optional[str] = None,
    node_a: Optional[str] = None,
    node_b: Optional[str] = None,
    adapter_a: int = 0,
    port_a: int = 0,
    adapter_b: int = 0,
    port_b: int = 0,
    filters: Optional[dict] = None,
) -> Any:
    """Enlaces: action=list|add|update|delete|filters.

    add    — exige node_a y node_b (adaptadores/puertos por defecto 0).
    update — exige link_id y `filters` (p. ej. {"latency": 50, "packet_loss": 5,
             "corrupt": 0, "frequency_drop": 0, "jitter": 0}).
    """
    pid, _ = _resolve_project(project_id, project_name)
    if not pid:
        return {"error": "proyecto no encontrado"}
    err = _ensure_open(pid)
    if err:
        return {"error": "no se pudo abrir el proyecto", "detail": err}
    action = action.lower()

    if action == "list":
        links = _api("GET", f"/v2/projects/{pid}/links") or []
        nodes = {n["node_id"]: n["name"] for n in _nodes(pid)}
        out = []
        for l in links if isinstance(links, list) else []:
            ends = []
            for e in l.get("nodes", []):
                ends.append({
                    "node": nodes.get(e.get("node_id"), e.get("node_id")),
                    "adapter": e.get("adapter_number"),
                    "port": e.get("port_number"),
                })
            out.append({"link_id": l.get("link_id"), "ends": ends, "capturing": l.get("capturing"),
                        "filters": l.get("filters")})
        return out

    if action == "add":
        if not (node_a and node_b):
            return {"error": "node_a y node_b son obligatorios"}
        nodes = _nodes(pid)
        ma, mb = _match_nodes(nodes, node_a), _match_nodes(nodes, node_b)
        if not ma or not mb:
            return {"error": "nodo no encontrado", "available": [n["name"] for n in nodes]}
        body = {"nodes": [
            {"node_id": ma[0]["node_id"], "adapter_number": adapter_a, "port_number": port_a},
            {"node_id": mb[0]["node_id"], "adapter_number": adapter_b, "port_number": port_b},
        ]}
        link = _api("POST", f"/v2/projects/{pid}/links", body)
        return link if not isinstance(link, dict) or not link.get("error") else link

    if action == "update":
        if not link_id:
            return {"error": "update exige link_id"}
        if filters is None:
            return {"error": "update exige filters (latency, packet_loss, corrupt, "
                             "frequency_drop, jitter)"}
        try:
            st, res = _client().link_update(pid, link_id, {"filters": filters})
        except ConnectionError as e:
            return {"error": str(e)}
        if st not in (200, 201):
            return _err_msg(st, res, "actualizar enlace")
        out = {"updated": True, "link_id": link_id}
        out["filters"] = (res or {}).get("filters", filters) if isinstance(res, dict) else filters
        return out

    if action == "delete":
        if not link_id:
            return {"error": "link_id es obligatorio"}
        try:
            st, res = _client().link_delete(pid, link_id)
        except ConnectionError as e:
            return {"error": str(e)}
        out = {"deleted": st in (200, 204), "link_id": link_id}
        if not out["deleted"]:
            out.update(_err_msg(st, res, "borrar enlace"))
        return out

    if action == "filters":
        if not link_id:
            return {"error": "filters exige link_id"}
        try:
            st, res = _client().link_available_filters(pid, link_id)
        except ConnectionError as e:
            return {"error": str(e)}
        return res if st == 200 else _err_msg(st, res, "obtener filtros del enlace")

    return {"error": f"acción desconocida: {action}", "valid": ["list", "add", "update", "delete", "filters"]}


@mcp.tool
def gns3_link_edit(
    action: str = "add",
    node_a: Optional[str] = None,
    node_b: Optional[str] = None,
    adapter_a: int = 0,
    adapter_b: int = 0,
    port_a: int = 0,
    port_b: int = 0,
    link_id: Optional[str] = None,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
) -> Any:
    """Enlaces con validación previa: action=add|delete|list.

    add     — node_a/node_b (nombre o id) y puertos `adapter_*`/`port_*` (0 por defecto).
              Antes de enviar comprueba el puerto contra los del nodo: un `ethernet_switch`
              tiene sus 8 puertos en el **adapter 0**, y un adapter mal puesto produciría
              `404 Port X/0 for SW1 not found`. La tool lo explica en vez de propagarlo.
    delete  — por `link_id` (admite prefijo único) o por node_a+node_b si el enlace es único.
    list    — enlaces con sus extremos (nodo, adapter, port).
    """
    action = action.lower()
    client = _client()
    proj, err = _pid_or_error(client, project_id, project_name)
    if err:
        return err
    pid = proj["project_id"]

    def ends_of(link: dict, names: dict) -> list[dict]:
        return [{"node": names.get(e.get("node_id"), e.get("node_id")),
                 "adapter": e.get("adapter_number"), "port": e.get("port_number")}
                for e in link.get("nodes", [])]

    if action == "list":
        names = {n["node_id"]: n["name"] for n in client.nodes(pid)}
        return [{"link_id": l.get("link_id"), "ends": ends_of(l, names),
                 "capturing": l.get("capturing")} for l in client.links(pid)]

    if action == "add":
        if not (node_a and node_b):
            return {"error": "add exige node_a y node_b"}
        try:
            a = client.find_node(pid, node_a)
            b = client.find_node(pid, node_b)
        except SystemExit as e:
            return {"error": str(e)}
        for side, node, adapter, port in (("a", a, adapter_a, port_a),
                                          ("b", b, adapter_b, port_b)):
            bad = _endpoint_error(node, adapter, port, side)
            if bad:
                return bad
        links = client.links(pid)
        names = {n["node_id"]: n["name"] for n in client.nodes(pid)}
        for l in links:
            ep = {(e.get("node_id"), e.get("adapter_number"), e.get("port_number"))
                  for e in l.get("nodes", [])}
            if ((a["node_id"], adapter_a, port_a) in ep
                    and (b["node_id"], adapter_b, port_b) in ep):
                return {"error": f"ya existe un enlace {a['name']}:{adapter_a}/{port_a} "
                                 f"<-> {b['name']}:{adapter_b}/{port_b}",
                        "link_id": l.get("link_id")}
        for side, node, adapter, port in (("a", a, adapter_a, port_a),
                                          ("b", b, adapter_b, port_b)):
            for l in links:
                ep = {(e.get("node_id"), e.get("adapter_number"), e.get("port_number"))
                      for e in l.get("nodes", [])}
                if (node["node_id"], adapter, port) in ep:
                    return {"error": f"el puerto {node['name']}:{adapter}/{port} ya está usado "
                                     f"por el enlace {l.get('link_id')} ({ends_of(l, names)})",
                            "link_id": l.get("link_id")}
        body = {"nodes": [
            {"node_id": a["node_id"], "adapter_number": adapter_a, "port_number": port_a},
            {"node_id": b["node_id"], "adapter_number": adapter_b, "port_number": port_b},
        ]}
        st, res = client.post(f"/v2/projects/{pid}/links", body, timeout=60)
        if st not in (200, 201):
            out = _err_msg(st, res, "crear enlace")
            if "not found" in out["error"]:
                out["hint"] = ("el puerto no existe en el nodo; en un ethernet_switch todos los "
                               "puertos están en adapter 0 (port 0-7)")
            return out
        res = res if isinstance(res, dict) else {}
        return {"link_id": res.get("link_id"),
                "ends": [{"node": a["name"], "adapter": adapter_a, "port": port_a},
                         {"node": b["name"], "adapter": adapter_b, "port": port_b}]}

    if action == "delete":
        links = client.links(pid)
        target = None
        if link_id:
            hits = [l for l in links if l.get("link_id") == link_id] or [
                l for l in links if str(l.get("link_id", "")).startswith(link_id)]
            if len(hits) != 1:
                return {"error": f"enlace no encontrado o ambiguo: {link_id}",
                        "available": [l.get("link_id") for l in links]}
            target = hits[0]
        elif node_a and node_b:
            try:
                a = client.find_node(pid, node_a)
                b = client.find_node(pid, node_b)
            except SystemExit as e:
                return {"error": str(e)}
            hits = [l for l in links
                    if {a["node_id"], b["node_id"]} <= {e.get("node_id") for e in l.get("nodes", [])}]
            if len(hits) != 1:
                return {"error": f"hay {len(hits)} enlaces entre {a['name']} y {b['name']}; "
                                 f"indica link_id",
                        "available": [l.get("link_id") for l in hits]}
            target = hits[0]
        else:
            return {"error": "delete exige link_id o node_a+node_b"}
        st, res = client.delete(f"/v2/projects/{pid}/links/{target['link_id']}", timeout=60)
        ok = st in (200, 204)
        out = {"deleted": ok, "link_id": target["link_id"]}
        if not ok:
            out.update(_err_msg(st, res, "borrar enlace"))
        return out

    return {"error": f"acción desconocida: {action}", "valid": ["add", "delete", "list"]}


@mcp.tool
def gns3_topology(project_id: Optional[str] = None, project_name: Optional[str] = None) -> dict:
    """Resumen legible de la topología: nodos con estado y enlaces con sus extremos."""
    pid, proj = _resolve_project(project_id, project_name)
    if not pid:
        return {"error": "proyecto no encontrado"}
    err = _ensure_open(pid)
    if err:
        return {"error": "no se pudo abrir el proyecto", "detail": err}
    nodes = _nodes(pid)
    links = _api("GET", f"/v2/projects/{pid}/links") or []
    names = {n["node_id"]: n["name"] for n in nodes}
    started = sum(1 for n in nodes if n.get("status") == "started")
    edges = []
    for l in links if isinstance(links, list) else []:
        ends = l.get("nodes", [])
        if len(ends) == 2:
            a = f"{names.get(ends[0]['node_id'], '?')}:{ends[0].get('adapter_number')}/{ends[0].get('port_number')}"
            b = f"{names.get(ends[1]['node_id'], '?')}:{ends[1].get('adapter_number')}/{ends[1].get('port_number')}"
            edges.append(f"{a} <-> {b}")
    return {
        "project": proj.get("name") if proj else pid,
        "status": proj.get("status") if proj else None,
        "nodes_total": len(nodes),
        "nodes_started": started,
        "nodes": [f"{n['name']} [{n.get('node_type')}] {n.get('status')} console={n.get('console')}" for n in nodes],
        "links_total": len(edges),
        "links": edges,
    }


@mcp.tool
def gns3_console(
    node: str,
    commands: list[str],
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    settle: float = 1.5,
    timeout: float = 20.0,
    ready_timeout: float = 30.0,
) -> dict:
    """Alias compatible de `gns3_exec`: consola telnet de un nodo, sin esperas ciegas.

    Se conserva la firma antigua (`settle` = quietud exigida a la salida de cada comando,
    no un `sleep` fijo) y la forma `{node, host, port, commands, output}`, pero toda la
    lectura la hace `core.Console` vía `gns3_exec`: corta por prompt/quietud, responde a
    `--More--` y a `[y/n]`, y devuelve la salida limpia de cada comando. Para el detalle
    por comando usa `gns3_exec`.
    """
    res = gns3_exec(
        node=node,
        commands=commands,
        project_id=project_id,
        project_name=project_name,
        idle=settle,
        timeout=timeout,
        ready_timeout=ready_timeout,
    )
    if isinstance(res, dict) and res.get("error"):
        return res
    results = res.get("results") or []
    output = "\n".join(r.get("output", "") for r in results if r.get("output"))
    return {
        "node": res.get("node"),
        "host": (res.get("console") or {}).get("host"),
        "port": (res.get("console") or {}).get("port"),
        "commands": commands,
        "output": output,
    }


@mcp.tool
def gns3_console_control(
    node: Optional[str] = None,
    action: str = "reset",
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    confirm: bool = False,
) -> Any:
    """Consola de un nodo: action=reset|reset-all|url.

    reset y reset-all reinician el proxy de consola (no el invitado) y exigen
    `confirm=True`; reset-all no exige `node`. url devuelve la URL WebSocket expuesta
    por el nodo sin abrir VNC.
    """
    action = action.lower()
    if action not in ("reset", "reset-all", "url"):
        return {"error": f"acción desconocida: {action}", "valid": ["reset", "reset-all", "url"]}
    if action in ("reset", "reset-all") and not confirm:
        return {"error": f"{action} de la consola exige confirm=True"}
    if action != "reset-all" and not node:
        return {"error": f"action={action} exige node"}
    client = _client()
    proj, err = _pid_or_error(client, project_id, project_name)
    if err:
        return err
    if action == "reset-all":
        try:
            st, res = client.nodes_console_reset(proj["project_id"])
        except ConnectionError as e:
            return {"error": str(e)}
        if st not in (200, 201, 204):
            return _api_error(st, res, "resetear todas las consolas")
        return {"reset": True, "scope": "all", "project": proj["name"], "detail": res}
    try:
        target = client.find_node(proj["project_id"], node)
    except (SystemExit, ConnectionError, RuntimeError) as e:
        return {"error": str(e)}
    nid = target["node_id"]
    if action == "url":
        try:
            url = client.console_ws_url(proj["project_id"], nid)
        except (ConnectionError, RuntimeError) as e:
            return {"error": str(e)}
        if not url:
            return {"error": f"{target['name']} no expone URL de consola WebSocket"}
        return {"node": target["name"], "url": url}
    try:
        st, res = client.console_reset(proj["project_id"], nid)
    except ConnectionError as e:
        return {"error": str(e)}
    if st not in (200, 201, 204):
        return _err_msg(st, res, "resetear consola")
    return {"reset": True, "node": target["name"], "detail": res}


@mcp.tool
def gns3_capture(
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    action: str = "start",
    link_id: Optional[str] = None,
    node_a: Optional[str] = None,
    node_b: Optional[str] = None,
    summary_lines: int = 40,
    file_name: Optional[str] = None,
) -> Any:
    """Captura de un enlace: action=start|stop|read.

    start/stop/read exigen link_id o (node_a y node_b) para localizarlo. `file_name` fija
    el nombre del pcap en el proyecto (por defecto `capture-<link_id>.pcap`); `read` resume
    el pcap con tshark.
    """
    pid, _ = _resolve_project(project_id, project_name)
    if not pid:
        return {"error": "proyecto no encontrado"}
    err = _ensure_open(pid)
    if err:
        return {"error": "no se pudo abrir el proyecto", "detail": err}
    if not link_id:
        if not (node_a and node_b):
            return {"error": "indica link_id o node_a+node_b"}
        links = _api("GET", f"/v2/projects/{pid}/links") or []
        names = {n["node_id"]: n["name"] for n in _nodes(pid)}
        for l in links if isinstance(links, list) else []:
            endnames = [names.get(e["node_id"]) for e in l.get("nodes", [])]
            if {node_a.lower(), node_b.lower()} <= {str(x).lower() for x in endnames if x}:
                link_id = l["link_id"]
                break
        if not link_id:
            return {"error": "no se encontró el enlace entre esos nodos"}

    action = action.lower()
    client = _client()
    if action == "start":
        try:
            st, res = client.link_capture(pid, link_id, "start", file_name)
        except ConnectionError as e:
            return {"error": str(e)}
        out = {"started": st in (200, 201), "link_id": link_id,
               "file_name": file_name or f"capture-{link_id[:8]}.pcap", "detail": res}
        if st not in (200, 201):
            out.update(_err_msg(st, res, "iniciar captura"))
        return out
    if action == "stop":
        try:
            st, res = client.link_capture(pid, link_id, "stop")
        except ConnectionError as e:
            return {"error": str(e)}
        out = {"stopped": st in (200, 201), "link_id": link_id, "detail": res}
        if st not in (200, 201):
            out.update(_err_msg(st, res, "parar captura"))
        return out

    if action == "read":
        try:
            st, pcap = client.link_capture(pid, link_id, "pcap")
        except ConnectionError as e:
            return {"error": str(e)}
        if st != 200 or not isinstance(pcap, bytes):
            # 409 cuando la captura ya se paró: el fichero sigue en disco dentro del proyecto
            download_error = _err_msg(st, pcap, "leer pcap")
            try:
                proj = client.project_get(pid)
            except (ConnectionError, RuntimeError) as e:
                return {"error": "no se pudo descargar el pcap", "detail": download_error,
                        "project_error": str(e)}
            base = Path(proj.get("path", "")) if isinstance(proj, dict) else None
            cands = sorted(
                (base / "project-files" / "captures").glob("*.pcap"),
                key=lambda p: p.stat().st_mtime, reverse=True,
            ) if base and base.exists() else []
            if not cands:
                return {"error": "no se pudo descargar el pcap y no hay ficheros en project-files/captures",
                        "detail": download_error}
            pcap = cands[0].read_bytes()
        out_dir = Path(os.path.expanduser("~/GNS3/captures"))
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"cap-{int(time.time())}-{link_id[:8]}.pcap"
        path.write_bytes(pcap)
        res = {"path": str(path), "bytes": len(pcap)}
        if subprocess.run(["bash", "-lc", "command -v tshark"], capture_output=True).returncode == 0:
            p = subprocess.run(
                ["tshark", "-r", str(path), "-c", str(summary_lines)],
                capture_output=True, text=True, timeout=60,
            )
            res["summary"] = p.stdout or p.stderr
        return res

    return {"error": f"acción desconocida: {action}"}


@mcp.tool
def gns3_nio(
    node: str,
    adapter: int,
    port: int,
    action: str = "get",
    nio: Optional[dict] = None,
    emulator: Optional[str] = None,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
) -> Any:
    """NIO de un puerto del compute: action=get|set|delete.

    `set` recibe el schema del NIO en `nio` (p. ej. nio_udp). Para cambiar los extremos
    UDP de un NIO existente, GNS3 exige borrarlo y crearlo de nuevo.
    """
    action = action.lower()
    if action not in ("get", "set", "delete"):
        return {"error": f"acción de NIO desconocida: {action}", "valid": ["get", "set", "delete"]}
    if action == "set" and not isinstance(nio, dict):
        return {"error": "action=set exige nio (dict)"}
    if not isinstance(adapter, int) or not isinstance(port, int) or adapter < 0 or port < 0:
        return {"error": "adapter y port deben ser enteros no negativos"}
    client = _client()
    proj, err = _pid_or_error(client, project_id, project_name)
    if err:
        return err
    try:
        target = client.find_node(proj["project_id"], node)
    except (SystemExit, ConnectionError, RuntimeError) as e:
        return {"error": str(e)}
    bad = _endpoint_error(target, adapter, port)
    if bad:
        return bad
    try:
        st, res = client.port_nio(
            proj["project_id"], target["node_id"], adapter, port,
            body=nio if action == "set" else None,
            emulator=emulator,
            delete=action == "delete",
        )
    except (ConnectionError, RuntimeError) as e:
        return {"error": str(e)}
    if st not in (200, 201, 204):
        return _api_error(st, res, f"{action} NIO")
    if action == "delete":
        return {"deleted": True, "node": target["name"], "adapter": adapter, "port": port}
    if action == "set":
        return res if res is not None else {"updated": True}
    return res


@mcp.tool
def gns3_port_capture(
    node: str,
    adapter: int,
    port: int,
    action: str = "start",
    file_name: Optional[str] = None,
    emulator: Optional[str] = None,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
) -> Any:
    """Captura de un puerto del compute: action=start|stop|pcap.

    `pcap` devuelve los bytes reales codificados en base64; no abre VNC ni modifica el nodo.
    """
    action = action.lower()
    actions = {"start": "start_capture", "stop": "stop_capture", "pcap": "pcap"}
    if action not in actions:
        return {"error": f"acción de captura desconocida: {action}",
                "valid": ["start", "stop", "pcap"]}
    if not isinstance(adapter, int) or not isinstance(port, int) or adapter < 0 or port < 0:
        return {"error": "adapter y port deben ser enteros no negativos"}
    client = _client()
    proj, err = _pid_or_error(client, project_id, project_name)
    if err:
        return err
    try:
        target = client.find_node(proj["project_id"], node)
    except (SystemExit, ConnectionError, RuntimeError) as e:
        return {"error": str(e)}
    bad = _endpoint_error(target, adapter, port)
    if bad:
        return bad
    try:
        st, res = client.port_capture(
            proj["project_id"], target["node_id"], adapter, port, actions[action],
            file_name=file_name, emulator=emulator,
        )
    except (ConnectionError, RuntimeError) as e:
        return {"error": str(e)}
    if st not in (200, 201, 204):
        return _api_error(st, res, f"{action} captura de puerto")
    if action == "pcap":
        if not isinstance(res, bytes):
            return _api_error(st, res, "leer pcap de puerto")
        return {"node": target["name"], "adapter": adapter, "port": port,
                "bytes": len(res), "content_base64": base64.b64encode(res).decode("ascii")}
    if res is not None:
        return res
    return {"started": True} if action == "start" else {"stopped": True}


@mcp.tool
def gns3_snapshots(
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    action: str = "list",
    name: Optional[str] = None,
    snapshot_id: Optional[str] = None,
    stop_nodes: bool = False,
) -> Any:
    """Snapshots del proyecto: action=list|create|restore|delete.
    GNS3 exige el proyecto parado para crear o restaurar: con stop_nodes=True se paran los nodos,
    se hace la operación y se vuelven a arrancar los que estaban started."""
    pid, _ = _resolve_project(project_id, project_name)
    if not pid:
        return {"error": "proyecto no encontrado"}
    err = _ensure_open(pid)
    if err:
        return {"error": "no se pudo abrir el proyecto", "detail": err}
    action = action.lower()
    client = _client()

    restart: list[str] = []
    restart_failed: list[dict] = []
    stop_failed: list[dict] = []
    if stop_nodes and action in ("create", "restore"):
        for n in _nodes(pid):
            if n.get("status") == "started":
                nid = n["node_id"]
                restart.append(nid)
                try:
                    st, res = client.node_action(pid, nid, "stop")
                except ConnectionError as e:
                    stop_failed.append({"node_id": nid, "error": str(e)})
                    continue
                if st not in (200, 201):
                    stop_failed.append({"node_id": nid,
                                        "error": _err_msg(st, res, "parar nodo")["error"]})
        if restart:
            time.sleep(1)

    def restart_nodes() -> None:
        for nid in restart:
            try:
                st, res = client.node_action(pid, nid, "start")
            except ConnectionError as e:
                restart_failed.append({"node_id": nid, "error": str(e)})
                continue
            if st not in (200, 201):
                restart_failed.append({"node_id": nid,
                                       "error": _err_msg(st, res, "arrancar nodo")["error"]})

    def with_restart(out: dict) -> dict:
        if restart_failed:
            out["restart_failed"] = restart_failed
        return out

    if stop_failed:
        restart_nodes()
        return with_restart({"error": stop_failed[0]["error"], "stop_failed": stop_failed})

    if action == "list":
        try:
            snaps = client.snapshots(pid)
        except ConnectionError as e:
            return {"error": str(e)}
        snaps, list_error = _verified_list(client, f"/v2/projects/{pid}/snapshots",
                                           snaps, "listar snapshots")
        if list_error:
            return list_error
        return [{"name": s.get("name"), "snapshot_id": s.get("snapshot_id"), "created_at": s.get("created_at")}
                for s in snaps]
    if action == "create":
        try:
            st, res = client.snapshot_create(pid, name or f"snap-{int(time.time())}")
        except ConnectionError as e:
            out = {"error": str(e)}
        else:
            out = ((res if isinstance(res, dict) else {"detail": res})
                   if st in (200, 201) else _err_msg(st, res, "crear snapshot"))
        finally:
            restart_nodes()
        return with_restart(out)
    if action in ("restore", "delete"):
        if not snapshot_id:
            try:
                snaps = client.snapshots(pid)
            except ConnectionError as e:
                restart_nodes()
                return with_restart({"error": str(e)})
            snaps, list_error = _verified_list(client, f"/v2/projects/{pid}/snapshots",
                                               snaps, "listar snapshots")
            if list_error:
                restart_nodes()
                return with_restart(list_error)
            match = next((s for s in snaps if str(s.get("name", "")).lower() == (name or "").lower()), None)
            if not match:
                restart_nodes()
                return with_restart({"error": "snapshot no encontrado",
                                     "available": [s.get("name") for s in snaps]})
            snapshot_id = match["snapshot_id"]
        try:
            if action == "restore":
                st, res = client.snapshot_restore(pid, snapshot_id)
            else:
                st, res = client.snapshot_delete(pid, snapshot_id)
        except ConnectionError as e:
            out = {"error": str(e)}
        else:
            if action == "delete":
                out = {"deleted": st in (200, 204), "snapshot_id": snapshot_id}
                if not out["deleted"]:
                    out.update(_err_msg(st, res, "borrar snapshot"))
            else:
                out = ((res if isinstance(res, dict) else {"detail": res})
                       if st in (200, 201) else _err_msg(st, res, "restaurar snapshot"))
        finally:
            restart_nodes()
        return with_restart(out)
    return {"error": f"acción desconocida: {action}"}


@mcp.tool
def gns3_images(emulator: str = "qemu") -> Any:
    """Imágenes disponibles en el compute local para un emulador (qemu por defecto)."""
    client = _client()
    try:
        imgs = client.images(emulator)
    except ConnectionError as e:
        return {"error": str(e)}
    emulator = emulator.removesuffix("/images")
    imgs, list_error = _verified_list(client, f"/v2/computes/local/{emulator}/images",
                                      imgs, "listar imágenes")
    if list_error:
        return list_error
    return [{"filename": i.get("filename"), "size_mb": round(i.get("filesize", 0) / 1048576, 1), "md5": i.get("md5sum")}
            for i in imgs if not i.get("filename", "").endswith(".md5sum")]


@mcp.tool
def gns3_node_files(
    node: str,
    path: str,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    content: Optional[str] = None,
) -> Any:
    """Lee (sin content) o escribe (con content) un fichero dentro del directorio de un nodo."""
    pid, _ = _resolve_project(project_id, project_name)
    if not pid:
        return {"error": "proyecto no encontrado"}
    err = _ensure_open(pid)
    if err:
        return {"error": "no se pudo abrir el proyecto", "detail": err}
    targets = _match_nodes(_nodes(pid), node)
    if not targets:
        return {"error": f"nodo no encontrado: {node}"}
    nid = targets[0]["node_id"]
    if content is None:
        got = core.node_file_read(core.Client(_conf()["url"],
                                              (_conf()["user"], _conf()["password"])), pid, nid, path)
        return {"node": targets[0]["name"], "path": path,
                **({"error": got["error"]} if isinstance(got, dict) else {"content": got})}
    res = core.node_file_write(core.Client(_conf()["url"],
                                           (_conf()["user"], _conf()["password"])), pid, nid, path, content)
    return {"node": targets[0]["name"], "path": path, **res}


@mcp.tool
def gns3_server_paths() -> dict:
    """Rutas y binarios que usa el servidor local (imágenes, proyectos, ubridge)."""
    c = _conf()
    return {
        "conf": str(CONF),
        "url": c["url"],
        "images_path": c.get("images_path"),
        "projects_path": c.get("projects_path"),
        "appliances_path": c.get("appliances_path"),
        "configs_path": c.get("configs_path"),
        "ubridge_path": c.get("ubridge_path"),
        "ubridge_exists": os.path.exists(c.get("ubridge_path") or ""),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Tools nuevas (núcleo compartido gns3core): consola robusta, monitor QEMU,
# edición de nodos, subida de imágenes, drawings y export/import.
# ══════════════════════════════════════════════════════════════════════════════
def _client():
    """Cliente del núcleo, con la misma conf que el resto de tools."""
    c = _conf()
    auth = (c["user"], c["password"]) if c.get("user") else None
    return core.Client(c["url"], auth)


def _pid_or_error(client, project_id, project_name):
    try:
        proj = client.resolve_project(project_id or project_name)
        client.ensure_open(proj["project_id"])
    except (SystemExit, ConnectionError, RuntimeError) as e:
        return None, {"error": str(e)}
    return proj, None


@mcp.tool
def gns3_exec(
    node: str,
    commands: list[str],
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    expect: Optional[str] = None,
    idle: float = 0.9,
    timeout: float = 20.0,
    answers: Optional[list[str]] = None,
    password: Optional[str] = None,
    wait_ready: bool = True,
    ready_timeout: float = 30.0,
) -> dict:
    """Ejecuta comandos en la consola telnet de un nodo, por prompt o por quietud.

    Es la única vía de consola: `gns3_console` es un alias compatible que delega aquí.
    No espera un tiempo fijo, responde solo a `--More--` y a `[y/n]`, y devuelve la salida
    de cada comando por separado. Si el nodo tiene consola gráfica (VNC), lo dice y remite
    a `gns3_monitor` en vez de fallar sin explicación.

    `expect` es una regex que cierra la lectura (p. ej. `r"\\$ $"`); sin ella se corta
    cuando la salida lleva `idle` segundos quieta. `password` se usa si aparece un
    prompt de contraseña. `wait_ready` pulsa Enter y espera shell (útil tras arrancar).
    """
    client = _client()
    proj, err = _pid_or_error(client, project_id, project_name)
    if err:
        return err
    try:
        node_obj = client.find_node(proj["project_id"], node)
    except SystemExit as e:
        return {"error": str(e)}
    if node_obj.get("status") != "started":
        return {"error": f"{node_obj['name']} no está arrancado (status={node_obj.get('status')}) "
                         f"→ gns3_nodes(action='start', node=...)"}
    try:
        con = core.console_for(client, proj["project_id"], node_obj)
    except core.ConsoleError as e:
        return {"error": str(e), "console_type": node_obj.get("console_type"),
                "hint": "gns3_monitor(node=..., action='text') para leer la pantalla"}
    try:
        ready = con.wait_ready(timeout=ready_timeout) if wait_ready else {"ready": None, "prompt": None}
        results = con.run_many(list(commands), expect=expect, idle=idle, timeout=timeout,
                               answers=answers, password=password)
    except core.ConsoleError as e:
        return {"error": str(e), "node": node_obj["name"]}
    finally:
        con.close()
    return {
        "project": proj["name"],
        "node": node_obj["name"],
        "console": {"type": node_obj.get("console_type"), "port": node_obj.get("console"),
                    "host": node_obj.get("console_host") or "127.0.0.1"},
        "prompt": ready.get("prompt"),
        "ready": ready.get("ready"),
        "results": results,
        "failed": [r["cmd"] for r in results if not r["ok"]],
    }


@mcp.tool
def gns3_monitor(
    node: str,
    action: str = "text",
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    keys: Optional[list[str]] = None,
    text: Optional[str] = None,
    dest: Optional[str] = None,
    scale: int = 2,
    psm: int = 4,
    delay: float = 0.08,
) -> dict:
    """Canal HMP del nodo QEMU: leer la pantalla real y pulsar teclas sin VNC.

    action:
      text   — screendump + OCR: devuelve el texto que hay en pantalla (lo más útil).
      shot   — solo screendump: PNG en `dest` o ~/GNS3/captures.
      type   — escribe `text` traduciendo cada carácter a `sendkey` (menús, login).
      key    — pulsa `keys` por nombre HMP (`ret`, `down`, `shift-2`, `f2`).
      status — `info status` (running/paused).
      cmd    — comando HMP crudo en `text` (p. ej. `system_reset`, `info network`).
      reset  — `system_reset`.

    Este es el sustituto del VNC: `screendump` no pierde teclas y `sendkey` no depende
    del foco de la ventana. El OCR lee a escala x2 con psm 4 (x1 confunde `w`/`u`).
    """
    client = _client()
    proj, err = _pid_or_error(client, project_id, project_name)
    if err:
        return err
    try:
        node_obj = client.find_node(proj["project_id"], node)
    except SystemExit as e:
        return {"error": str(e)}
    if node_obj.get("node_type") != "qemu":
        return {"error": f"{node_obj['name']} no es un nodo QEMU (es {node_obj.get('node_type')}); "
                         f"usa gns3_exec para consolas telnet"}
    disk = (node_obj.get("properties") or {}).get("hda_disk_image")
    try:
        mon = core.QemuMonitor.for_node(node_id=node_obj["node_id"], disk=disk)
    except RuntimeError as e:
        return {"error": str(e), "node": node_obj["name"], "status": node_obj.get("status")}
    try:
        action = action.lower()
        out: dict = {"node": node_obj["name"], "monitor_port": mon.port, "action": action}
        if action == "text":
            out.update(core.screen_text(mon, psm=psm, scale=scale))
        elif action == "shot":
            out.update(mon.screendump(dest=dest, scale=scale))
        elif action == "type":
            if text is None:
                return {"error": "action=type exige text"}
            out.update(mon.type_text(text, delay=delay))
            out["after"] = core.screen_text(mon, psm=psm, scale=scale).get("ocr", "")[-800:]
        elif action == "key":
            if not keys:
                return {"error": "action=key exige keys=['ret']"}
            out.update(mon.sendkey(*keys, delay=delay))
        elif action == "status":
            out.update(mon.run("info status"))
        elif action == "cmd":
            if not text:
                return {"error": "action=cmd exige text"}
            out.update(mon.run(text))
        elif action == "reset":
            out.update(mon.run("system_reset"))
        else:
            return {"error": f"acción desconocida: {action}",
                    "valid": ["text", "shot", "type", "key", "status", "cmd", "reset"]}
        return out
    finally:
        mon.close()


@mcp.tool
def gns3_node_edit(
    action: str = "update",
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    node: Optional[str] = None,
    template: Optional[str] = None,
    name: Optional[str] = None,
    node_type: Optional[str] = None,
    x: int = 0,
    y: int = 0,
    properties: Optional[dict] = None,
    ports_mapping: Optional[list[dict]] = None,
    symbol: Optional[str] = None,
    disk_image: Optional[str] = None,
    new_disk: Optional[str] = None,
    build_from: Optional[str] = None,
    size: Optional[int] = None,
    proposals: bool = False,
    confirm: bool = False,
) -> Any:
    """Crear, modificar, duplicar o borrar nodos; y operar sus discos y consola.

    action:
      create      — con `template` (nombre/id) o sin él: `node_type` + `properties`
                    (p. ej. qemu con hda_disk_image apuntando a un qcow2 ya instalado).
      update      — aplica `properties`, `ports_mapping`, `symbol` y/o `name` al nodo.
      delete      — borra el nodo.
      duplicate   — clona el nodo existente (nuevo node_id + disco enlazado).
      clone_disk  — copia `disk_image` (o el del nodo) a `new_disk` en images/QEMU y
                    repunta el nodo para no compartir disco entre nodos.
      switch      — atajo: `ports_mapping` como lista de dicts {name,type,vlan}.
      disk-resize — amplía el disco del nodo QEMU a `size` MiB; exige `confirm=True`.
      links       — enlaces conectados al nodo.
      idlepc      — valor idlepc automático; con `proposals=True`, las propuestas.
    """
    action = action.lower()
    if action == "disk-resize":
        if not confirm:
            return {"error": "disk-resize exige confirm=True"}
        if size is None or size <= 0:
            return {"error": "disk-resize exige size entero positivo (MiB)"}
    client = _client()
    proj, err = _pid_or_error(client, project_id, project_name)
    if err:
        return err
    pid = proj["project_id"]

    if action == "create":
        if template:
            tpl = next((t for t in client.templates()
                        if t.get("template_id") == template
                        or str(t.get("name", "")).lower() == template.lower()), None)
            if not tpl:
                return {"error": f"plantilla no encontrada: {template}",
                        "available": [t.get("name") for t in client.templates()]}
            st, res = client.post(f"/v2/projects/{pid}/templates/{tpl['template_id']}",
                                  {"x": x, "y": y, "compute_id": "local"})
        else:
            if not (node_type and properties):
                return {"error": "create sin plantilla exige node_type y properties"}
            body = {"name": name or f"{node_type}-{int(time.time())%10000}",
                    "node_type": node_type, "compute_id": "local", "x": x, "y": y,
                    "properties": properties}
            st, res = client.post(f"/v2/projects/{pid}/nodes", body, timeout=120)
        if st not in (200, 201):
            msg = res.get("message") if isinstance(res, dict) else res
            return {"error": f"no se pudo crear: [{st}] {msg}"}
        if name and isinstance(res, dict) and res.get("name") != name:
            client.put(f"/v2/projects/{pid}/nodes/{res['node_id']}", {"name": name})
            res["name"] = name
        return core.node_summary(res)

    if not node:
        return {"error": f"action={action} exige node"}
    try:
        target = client.find_node(pid, node)
    except SystemExit as e:
        return {"error": str(e)}
    nid = target["node_id"]

    if action == "delete":
        st, res = client.delete(f"/v2/projects/{pid}/nodes/{nid}", timeout=120)
        return {"deleted": st in (200, 204), "node": target["name"], "status": st}

    if action == "duplicate":
        st, res = client.post(f"/v2/projects/{pid}/nodes/{nid}/duplicate",
                              {"x": x, "y": y, "name": name}, timeout=180)
        if st not in (200, 201):
            msg = res.get("message") if isinstance(res, dict) else res
            return {"error": f"duplicate falló: [{st}] {msg}"}
        return core.node_summary(res)

    if action == "disk-resize":
        try:
            st, res = client.node_resize_disk(pid, nid, int(size))
        except ConnectionError as e:
            return {"error": str(e)}
        if st not in (200, 201, 204):
            return _err_msg(st, res, "redimensionar disco")
        return {"resized": True, "node": target["name"], "size_mb": size, "detail": res}

    if action == "links":
        try:
            links = client.node_links(pid, nid)
        except ConnectionError as e:
            return {"error": str(e)}
        links, list_error = _verified_list(client, f"/v2/projects/{pid}/nodes/{nid}/links",
                                           links, "listar enlaces del nodo")
        return list_error if list_error else links

    if action == "idlepc":
        try:
            st, res = client.node_idlepc(pid, nid, proposals)
        except ConnectionError as e:
            return {"error": str(e)}
        if st != 200:
            return _err_msg(st, res, "obtener idlepc")
        return {"node": target["name"], "proposals": proposals, "idlepc": res}

    if action in ("update", "switch"):
        NODE_LEVEL = {"name", "console", "console_type", "x", "y", "z", "symbol", "locked"}
        body: dict = {}
        props = dict(properties or {})
        # claves de nodo que no son propiedades: si viajan en `properties` la API
        # responde 200 y no cambia nada (pasa con `console`)
        for k in list(props):
            if k in NODE_LEVEL:
                body[k] = props.pop(k)
        if props:
            body["properties"] = props
        if ports_mapping is not None:
            body.setdefault("properties", {})["ports_mapping"] = ports_mapping
        if symbol:
            body["symbol"] = symbol
        if name:
            body["name"] = name
        if not body:
            return {"error": "update sin cambios: pasa properties, ports_mapping, symbol o name"}
        st, res = client.put(f"/v2/projects/{pid}/nodes/{nid}", body, timeout=120)
        if st not in (200, 201):
            msg = res.get("message") if isinstance(res, dict) else res
            return {"error": f"update falló: [{st}] {msg}"}
        return {"updated": True, "node": target["name"],
                "properties": (res or {}).get("properties", {})}

    if action == "clone_disk":
        src_name = disk_image or (target.get("properties") or {}).get("hda_disk_image")
        if not src_name:
            return {"error": "el nodo no tiene hda_disk_image; pasa disk_image"}
        images_dir = Path(os.path.expanduser("~/GNS3/images/QEMU"))
        src = images_dir / os.path.basename(src_name)
        if not src.exists():
            return {"error": f"no existe el disco origen {src}"}
        dst_name = new_disk or f"{src.stem}-{time.strftime('%H%M%S')}.qcow2"
        dst = images_dir / dst_name
        if dst.exists():
            return {"error": f"ya existe {dst}; elige otro new_disk"}
        qemu_img = shutil.which("qemu-img")
        if qemu_img:
            r = subprocess.run([qemu_img, "convert", "-O", "qcow2", str(src), str(dst)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                return {"error": f"qemu-img convert falló: {r.stderr.strip()[:300]}"}
            modo = "qemu-img convert"
        else:
            shutil.copy2(src, dst)          # copia completa, más lenta pero segura
            modo = "cp"
        st, res = client.put(f"/v2/projects/{pid}/nodes/{nid}",
                             {"properties": {"hda_disk_image": dst_name,
                                             "hda_disk_image_md5sum": "",
                                             "linked_clone": False}}, timeout=120)
        return {"copied": str(dst), "size_mb": round(dst.stat().st_size / 2**20, 1),
                "method": modo, "node": target["name"],
                "repointed": st in (200, 201), "disk": dst_name}

    return {"error": f"acción desconocida: {action}",
            "valid": ["create", "update", "switch", "delete", "duplicate", "clone_disk",
                      "disk-resize", "links", "idlepc"]}


@mcp.tool
def gns3_upload(path: str, name: Optional[str] = None, compress: bool = True,
                emulator: str = "qemu") -> dict:
    """Sube un disco/imagen (qcow2, iso) al compute local del servidor GNS3.

    Con `compress` un qcow2 pasa por `qemu-img convert -c` (2,3 GB → ~500 MB) antes de
    subir; es lo que hace viable portar un pfSense ya instalado por red. Verifica al
    final que el nombre aparece en la lista de imágenes del compute.
    """
    src = Path(path).expanduser()
    if not src.is_file():
        return {"error": f"no existe {src}"}
    target_name = name or src.name
    payload = src
    tmp = None
    if compress and src.suffix.lower() == ".qcow2":
        qemu_img = shutil.which("qemu-img")
        if qemu_img:
            tmp = Path("/tmp") / f"upload-{src.stem}.qcow2"
            r = subprocess.run([qemu_img, "convert", "-c", "-O", "qcow2", str(src), str(tmp)],
                               capture_output=True, text=True)
            if r.returncode == 0:
                payload = tmp
            else:
                tmp = None
    client = _client()
    data = payload.read_bytes()
    try:
        st, res = client.compute_write_file("local", emulator, target_name, data)
    except ConnectionError as e:
        return {"error": str(e)}
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)
    if st not in (200, 201, 204):
        msg = res.get("message") if isinstance(res, dict) else res
        return {"error": f"subida falló: [{st}] {msg}"}
    listed = [i.get("filename") for i in client.qemu_images()] if emulator == "qemu" else []
    return {"uploaded": target_name, "from": str(src), "bytes_sent": len(data),
            "compressed": payload != src, "verified_in_server": target_name in listed,
            "images": listed if not listed or target_name in listed else listed[:30]}


def _note_svg(text: Optional[str], width: int, height: int, color: str) -> str:
    """SVG de la nota del canvas (2.2.61 rechaza width/height como campos aparte)."""
    esc = (text or "").replace("&", "&amp;").replace("<", "&lt;")
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{width}" height="{height}" fill="none" stroke="{color}" '
        f'stroke-width="2" rx="6"/>'
        f'<text x="8" y="{min(22, height-8)}" font-size="14" fill="{color}">'
        f'{esc}</text></svg>'
    )


@mcp.tool
def gns3_drawings(
    action: str = "list",
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    x: Optional[int] = None,
    y: Optional[int] = None,
    text: Optional[str] = None,
    width: int = 220,
    height: int = 60,
    color: Optional[str] = None,
    rotation: int = 0,
    drawing_id: Optional[str] = None,
) -> Any:
    """Anotaciones del canvas: action=list|text|rect|update|clear|delete.

    Sirve para dejar el direccionamiento del enunciado escrito en el proyecto (el
    profesor lo ve al corregir) sin añadir nodos que ocupan consola.

    update — por `drawing_id`: mueve (`x`, `y`) y/o reescribe `text` y `color`. Conserva
             el tamaño y el texto que ya tenía la nota si no se pasan.
    """
    client = _client()
    proj, err = _pid_or_error(client, project_id, project_name)
    if err:
        return err
    pid = proj["project_id"]
    action = action.lower()

    if action == "list":
        try:
            res = client.drawings(pid)
        except ConnectionError as e:
            return {"error": str(e)}
        res, list_error = _verified_list(client, f"/v2/projects/{pid}/drawings",
                                         res, "listar drawings")
        return list_error if list_error else res

    if action == "clear":
        try:
            res = client.drawings(pid)
        except ConnectionError as e:
            return {"error": str(e)}
        res, list_error = _verified_list(client, f"/v2/projects/{pid}/drawings",
                                         res, "listar drawings")
        if list_error:
            return list_error
        borrados = 0
        for d in res:
            try:
                s2, _ = client.drawing_delete(pid, d["drawing_id"])
            except ConnectionError as e:
                return {"error": str(e), "deleted": borrados, "of": len(res)}
            borrados += 1 if s2 in (200, 204) else 0
        return {"deleted": borrados, "of": len(res)}

    if action == "delete":
        if not drawing_id:
            return {"error": "action=delete exige drawing_id"}
        try:
            st, res = client.drawing_delete(pid, drawing_id)
        except ConnectionError as e:
            return {"error": str(e)}
        out = {"deleted": st in (200, 204), "drawing_id": drawing_id}
        if not out["deleted"]:
            out.update(_err_msg(st, res, "borrar drawing"))
        return out

    if action == "update":
        if not drawing_id:
            return {"error": "action=update exige drawing_id"}
        try:
            st, cur = client.get(f"/v2/projects/{pid}/drawings/{drawing_id}")
        except ConnectionError as e:
            return {"error": str(e)}
        if st != 200 or not isinstance(cur, dict):
            return {"error": f"drawing no encontrado: {drawing_id}", "detail": cur}
        body: dict = {}
        if x is not None:
            body["x"] = x
        if y is not None:
            body["y"] = y
        if text is not None or color is not None:
            svg = str(cur.get("svg") or "")
            mw = re.search(r'width="(\d+)"', svg)
            mh = re.search(r'height="(\d+)"', svg)
            mt = re.search(r"<text[^>]*>(.*?)</text>", svg, re.S)
            mc = re.search(r'stroke="([^"]+)"', svg)
            old_text = html.unescape(mt.group(1)) if mt else ""
            new_text = text if text is not None else old_text
            body["svg"] = _note_svg(new_text,
                                    int(mw.group(1)) if mw else width,
                                    int(mh.group(1)) if mh else height,
                                    color or (mc.group(1) if mc else "#ffffff"))
        if not body:
            return {"error": "update sin cambios: pasa x, y, text o color"}
        try:
            st, res = client.drawing_update(pid, drawing_id, body)
        except ConnectionError as e:
            return {"error": str(e)}
        if st not in (200, 201):
            return _err_msg(st, res, "actualizar drawing")
        got = res if isinstance(res, dict) else {}
        return {"updated": True, "drawing_id": drawing_id,
                "x": got.get("x", body.get("x")), "y": got.get("y", body.get("y")),
                "text": new_text if "svg" in body else None, "drawing": res}

    if action in ("text", "rect"):
        if action == "text" and text is None:
            return {"error": "action=text exige text"}
        body = {
            "x": x if x is not None else 0, "y": y if y is not None else 0, "z": 0,
            "rotation": rotation,          # 2.2.61 rechaza width/height aquí
            "svg": _note_svg(text, width, height, color or "#ffffff"),
        }
        try:
            st, res = client.drawing_create(pid, body)
        except ConnectionError as e:
            return {"error": str(e)}
        if st not in (200, 201):
            return _err_msg(st, res, "crear drawing")
        return {"created": True, "drawing_id": (res or {}).get("drawing_id"), "text": text}

    return {"error": f"acción desconocida: {action}",
            "valid": ["list", "text", "rect", "update", "clear", "delete"]}


@mcp.tool
def gns3_project_io(
    action: str = "export",
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    path: Optional[str] = None,
    name: Optional[str] = None,
    open_after: bool = True,
) -> Any:
    """Export/import/duplicate/load de un proyecto (.gns3p).

    export    — descarga a `path` o ~/GNS3/exports/<nombre>-<fecha>.gns3p (para el examen:
                un proyecto esqueleto que se restaura en el servidor del aula).
    import    — sube un .gns3p; con `name` lo renombra y `open_after` lo abre.
    duplicate — duplica el proyecto mediante la API con `name` nuevo.
    load      — carga un proyecto desde una ruta del servidor (`path`).
    """
    action = action.lower()
    client = _client()
    if action == "load":
        if not path:
            return {"error": "action=load exige path"}
        try:
            st, res = client.project_load(path)
        except ConnectionError as e:
            return {"error": str(e)}
        return res if st in (200, 201) else _err_msg(st, res, "cargar proyecto")
    proj, err = _pid_or_error(client, project_id, project_name)
    if err:
        return err
    pid = proj["project_id"]

    def _export_bytes(stop_nodes: bool = True):
        """Exporta el proyecto, parando los nodos si hace falta.

        GNS3 devuelve 409 «Project must be stopped in order to export it» con nodos
        arrancados; se paran, se exporta y se vuelven a arrancar los que estaban.
        """
        estaban: list[str] = []
        if stop_nodes:
            for n in client.nodes(pid):
                if n.get("status") == "started":
                    estaban.append(n["node_id"])
                    client.post(f"/v2/projects/{pid}/nodes/{n['node_id']}/stop", timeout=180)
            if estaban:
                time.sleep(1)
        try:
            st, body = client.get(f"/v2/projects/{pid}/export", raw=True, timeout=300)
        finally:
            for nid in estaban:
                client.post(f"/v2/projects/{pid}/nodes/{nid}/start", timeout=180)
        if st != 200 or not isinstance(body, bytes) or not body.startswith(b"PK"):
            raise RuntimeError(f"export falló: [{st}] {body[:200]!r}")
        return body

    if action == "export":
        if not path:
            out_dir = Path(os.path.expanduser("~/GNS3/exports"))
            out_dir.mkdir(parents=True, exist_ok=True)
            safe = re.sub(r"[^\w.-]+", "-", proj["name"])
            path = str(out_dir / f"{safe}-{time.strftime('%Y%m%d-%H%M')}.gns3p")
        dest = Path(path).expanduser()
        dest.parent.mkdir(parents=True, exist_ok=True)
        body = _export_bytes()
        dest.write_bytes(body)
        return {"path": str(dest), "kb": round(len(body) / 1024), "project": proj["name"]}

    if action == "duplicate":
        try:
            st, res = client.project_duplicate(pid, name)
        except ConnectionError as e:
            return {"error": str(e)}
        return res if st in (200, 201) else _err_msg(st, res, "duplicar proyecto")

    if action == "import":
        if not path:
            return {"error": "action=import exige path"}
        src = Path(path).expanduser()
        if not src.is_file():
            return {"error": f"no existe {src}"}
        body = src.read_bytes()
        new_name = name
        nuevo = str(uuid.uuid4())
        st, res = client.req("POST", f"/v2/projects/{nuevo}/import", data=body,
                             ctype="application/gns3project", timeout=600)
        if st not in (200, 201):
            msg = res.get("message") if isinstance(res, dict) else res
            return {"error": f"import falló: [{st}] {msg}"}
        if new_name:
            client.put(f"/v2/projects/{nuevo}", {"name": new_name})
        opened = False
        if open_after:
            s2, _ = client.post(f"/v2/projects/{nuevo}/open", timeout=300)
            opened = s2 in (200, 201)
        return {"project_id": nuevo, "name": new_name or proj["name"],
                "kb": round(len(body) / 1024), "opened": opened,
                "nodes": len(client.nodes(nuevo)) if opened else None}

    return {"error": f"acción desconocida: {action}", "valid": ["export", "import", "duplicate", "load"]}


@mcp.tool
def gns3_project_stats(
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
) -> Any:
    """Estadísticas reales de un proyecto: nodos, enlaces y estado de sus recursos."""
    pid, _ = _resolve_project(project_id, project_name)
    if not pid:
        return {"error": "proyecto no encontrado", "project_id": project_id,
                "project_name": project_name}
    try:
        st, res = _client().project_stats(pid)
    except ConnectionError as e:
        return {"error": str(e)}
    return res if st == 200 else _err_msg(st, res, "obtener estadísticas del proyecto")


@mcp.tool
def gns3_project_files(
    action: str,
    path: str,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    content: Optional[str] = None,
) -> Any:
    """Ficheros del proyecto: action=get|put sobre `path`.

    get devuelve el contenido; put escribe `content` en crudo dentro del proyecto.
    """
    action = action.lower()
    if action not in ("get", "put"):
        return {"error": f"acción desconocida: {action}", "valid": ["get", "put"]}
    if not path:
        return {"error": "path es obligatorio"}
    if action == "put" and content is None:
        return {"error": "action=put exige content"}
    client = _client()
    proj, err = _pid_or_error(client, project_id, project_name)
    if err:
        return err
    pid = proj["project_id"]
    try:
        if action == "get":
            got = client.project_file_read(pid, path)
            if isinstance(got, dict) and got.get("error"):
                return {"path": path, **got}
            return {"project": proj["name"], "path": path, "content": got}
        st, res = client.project_file_write(pid, path, content)
    except ConnectionError as e:
        return {"error": str(e)}
    if st not in (200, 201, 204):
        return _err_msg(st, res, "escribir fichero del proyecto")
    return {"written": True, "project": proj["name"], "path": path, "detail": res}


def _pat_match(value: Any, pattern: Optional[str]) -> bool:
    """Coincidencia por glob si el patrón lo parece, por subcadena si no."""
    if not pattern:
        return True
    val, pat = str(value or "").lower(), pattern.lower()
    if any(ch in pat for ch in "*?["):
        return fnmatch.fnmatch(val, pat)
    return pat in val


@mcp.tool
def gns3_compute(
    cid: str = "local",
    action: str = "info",
    body: Optional[dict] = None,
    emulator: Optional[str] = None,
    operation: Optional[str] = None,
    confirm: bool = False,
) -> Any:
    """Computes: action=info|list|add|update|delete|ports|idlepc|call.

    info es el comportamiento original. add/update reciben `body`; update y delete
    exigen `confirm=True`. call invoca `/computes/{cid}/{emulator}/{operation}`;
    si lleva `body` (POST) también exige confirmación.
    """
    action = action.lower()
    valid = ["info", "list", "add", "update", "delete", "ports", "idlepc", "call"]
    if action not in valid:
        return {"error": f"acción desconocida: {action}", "valid": valid}
    if action in ("update", "delete") and not confirm:
        return {"error": f"{action} de compute exige confirm=True"}
    if action in ("add", "update") and not isinstance(body, dict):
        return {"error": f"{action} exige body (dict)"}
    if action == "call":
        if not (emulator and operation):
            return {"error": "call exige emulator y operation"}
        if body is not None and not confirm:
            return {"error": "call con body exige confirm=True"}
    client = _client()
    try:
        if action == "list":
            computes = client.computes()
            computes, list_error = _verified_list(client, "/v2/computes", computes, "listar computes")
            return list_error if list_error else computes
        if action == "info":
            info = client.compute(cid)
            if info:
                return info
            st, body = client.get(f"/v2/computes/{cid}")
            if st != 200:
                return _err_msg(st, body, "obtener compute")
            return {"error": f"compute no encontrado: {cid}"}
        if action == "add":
            st, res = client.compute_create(body)
            what = "crear compute"
        elif action == "update":
            st, res = client.compute_update(cid, body)
            what = "actualizar compute"
        elif action == "delete":
            st, res = client.compute_delete(cid)
            return {"deleted": st in (200, 204), "compute_id": cid,
                    **({} if st in (200, 204) else _err_msg(st, res, "borrar compute"))}
        elif action == "ports":
            st, res = client.compute_ports(cid)
            what = "obtener puertos del compute"
        elif action == "idlepc":
            st, res = client.compute_auto_idlepc(cid)
            what = "calcular idlepc del compute"
        else:
            st, res = client.compute_action(cid, emulator, operation, body)
            what = f"invocar {emulator}/{operation}"
    except ConnectionError as e:
        return {"error": str(e)}
    ok = st in (200, 201, 204)
    return (res if res is not None else {"ok": True}) if ok else _err_msg(st, res, what)


@mcp.tool
def gns3_statistics() -> Any:
    """Estadísticas de uso de cada compute: CPU, disco, RAM y swap."""
    client = _client()
    try:
        stats = client.statistics()
    except ConnectionError as e:
        return {"error": str(e)}
    stats, list_error = _verified_list(client, "/v2/statistics", stats, "listar estadísticas")
    return list_error if list_error else stats


@mcp.tool
def gns3_symbols(
    pattern: Optional[str] = None,
    action: str = "list",
    symbol_id: Optional[str] = None,
    path: Optional[str] = None,
    content: Optional[str] = None,
    confirm: bool = False,
) -> Any:
    """Símbolos: action=list|dimensions|raw|default|upload.

    list acepta `pattern` (glob o subcadena). dimensions/raw/upload exigen `symbol_id`.
    upload lee `path` o codifica `content`; al sobrescribir exige `confirm=True`.
    """
    action = action.lower()
    if action not in ("list", "dimensions", "raw", "default", "upload"):
        return {"error": f"acción desconocida: {action}",
                "valid": ["list", "dimensions", "raw", "default", "upload"]}
    client = _client()
    try:
        if action == "list":
            syms = client.symbols()
            syms, list_error = _verified_list(client, "/v2/symbols", syms, "listar símbolos")
            if list_error:
                return list_error
            return [
                {"filename": sym.get("filename"), "symbol_id": sym.get("symbol_id"),
                 "theme": sym.get("theme"), "builtin": sym.get("builtin")}
                for sym in syms
                if _pat_match(sym.get("filename"), pattern) or _pat_match(sym.get("symbol_id"), pattern)
            ]
        if action == "default":
            st, res = client.default_symbols()
            return res if st == 200 else _err_msg(st, res, "obtener símbolos por defecto")
        if not symbol_id:
            return {"error": f"{action} exige symbol_id"}
        if action == "dimensions":
            st, res = client.symbol_dimensions(symbol_id)
            return res if st == 200 else _err_msg(st, res, "obtener dimensiones del símbolo")
        if action == "raw":
            st, raw = client.symbol_raw(symbol_id)
            if st != 200 or not isinstance(raw, bytes):
                return _err_msg(st, raw, "obtener símbolo crudo")
            try:
                return {"symbol_id": symbol_id, "content": raw.decode("utf-8"), "bytes": len(raw)}
            except UnicodeDecodeError:
                return {"symbol_id": symbol_id, "content_base64": base64.b64encode(raw).decode("ascii"),
                        "bytes": len(raw)}
        if path and content is not None:
            return {"error": "upload acepta path o content, no ambos"}
        if not path and content is None:
            return {"error": "upload exige path o content"}
        if not confirm:
            return {"error": "subir un símbolo exige confirm=True"}
        if path:
            src = Path(path).expanduser()
            if not src.is_file():
                return {"error": f"no existe {src}"}
            data = src.read_bytes()
        else:
            data = content.encode("utf-8")
        st, res = client.symbol_raw_upload(symbol_id, data)
    except (ConnectionError, OSError) as e:
        return {"error": str(e)}
    if st not in (200, 201, 204):
        return _err_msg(st, res, "subir símbolo")
    return {"uploaded": True, "symbol_id": symbol_id, "bytes": len(data), "detail": res}


@mcp.tool
def gns3_appliances(pattern: Optional[str] = None) -> Any:
    """Appliances del servidor (`GET /v2/appliances`), filtrables por nombre, fabricante
    o categoría. Sin `pattern` devuelve todas; la descripción va recortada a 300 caracteres.
    """
    client = _client()
    try:
        apps = client.appliances()
    except ConnectionError as e:
        return {"error": str(e)}
    apps, list_error = _verified_list(client, "/v2/appliances", apps, "listar appliances")
    if list_error:
        return list_error
    out = []
    for a in apps:
        if not any(_pat_match(a.get(k), pattern)
                   for k in ("name", "product_name", "vendor_name", "category")):
            continue
        out.append({
            "name": a.get("name"),
            "product_name": a.get("product_name"),
            "category": a.get("category"),
            "vendor_name": a.get("vendor_name"),
            "status": a.get("status"),
            "symbol": a.get("symbol"),
            "description": str(a.get("description") or "")[:300],
        })
    return out


@mcp.tool
def gns3_node_action(
    node: str,
    action: str,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
) -> Any:
    """Arranca, para, reinicia, suspende o reanuda **un** nodo.

    action=start|stop|reload|suspend|resume|pause|unpause. `node` acepta nombre, patrón
    o node_id. Devuelve el estado real releído del nodo, no sólo el 200 del POST.
    Para una acción masiva usa `gns3_nodes_bulk`.
    """
    action = action.lower()
    if action not in ("start", "stop", "reload", "suspend", "resume", "pause", "unpause"):
        return {"error": f"acción de nodo desconocida: {action}",
                "valid": ["start", "stop", "reload", "suspend", "resume", "pause", "unpause"]}
    client = _client()
    proj, err = _pid_or_error(client, project_id, project_name)
    if err:
        return err
    try:
        target = client.find_node(proj["project_id"], node)
    except (SystemExit, ConnectionError, RuntimeError) as e:
        return {"error": str(e)}
    try:
        st, res = client.node_action(proj["project_id"], target["node_id"], action)
    except ConnectionError as e:
        return {"error": str(e)}
    if st not in (200, 201):
        return _err_msg(st, res, f"{action} de {target['name']}")
    time.sleep(0.8)
    try:
        detail = client.node_detail(proj["project_id"], target["node_id"])
    except (ConnectionError, RuntimeError) as e:
        return {"node": target["name"], "action": action, "request_ok": True,
                "status": None, "error": str(e)}
    return {"node": target["name"], "node_id": target["node_id"], "action": action,
            "request_ok": True, "status": detail.get("status")}


@mcp.tool
def gns3_command_line(
    node: str,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
) -> Any:
    """Línea de comandos con la que el servidor arranca el nodo (QEMU/dynamips/IOU).

    Es `command_line` del detalle del nodo: dice qué binario y qué flags usa, útil para
    depurar un arranque que no llega a consola.
    """
    client = _client()
    proj, err = _pid_or_error(client, project_id, project_name)
    if err:
        return err
    try:
        target = client.find_node(proj["project_id"], node)
    except (SystemExit, ConnectionError, RuntimeError) as e:
        return {"error": str(e)}
    try:
        line = client.node_command_line(proj["project_id"], target["node_id"])
    except (ConnectionError, RuntimeError) as e:
        return {"error": str(e)}
    out: dict = {"node": target["name"], "node_id": target["node_id"], "command_line": line}
    if not line:
        out["detail"] = ("el nodo no expone command_line (sólo qemu, dynamips e iou lo "
                         "tienen; docker, vpcs y los switches no)")
    return out


@mcp.tool
def gns3_gns3vm(
    action: str = "show",
    engine: Optional[str] = None,
    body: Optional[dict] = None,
) -> Any:
    """GNS3 VM: action=show|set|engines|vms.

    set aplica `body`; vms lista las máquinas virtuales de `engine`.
    """
    action = action.lower()
    if action not in ("show", "set", "engines", "vms"):
        return {"error": f"acción desconocida: {action}", "valid": ["show", "set", "engines", "vms"]}
    if action == "set" and not isinstance(body, dict):
        return {"error": "set exige body (dict)"}
    if action == "vms" and not engine:
        return {"error": "vms exige engine"}
    client = _client()
    try:
        if action == "show":
            st, res = client.gns3vm()
            what = "obtener GNS3 VM"
        elif action == "set":
            st, res = client.gns3vm_update(body)
            what = "actualizar GNS3 VM"
        elif action == "engines":
            st, res = client.gns3vm_engines()
            what = "listar motores de GNS3 VM"
        else:
            st, res = client.gns3vm_vms(engine)
            what = "listar máquinas virtuales"
    except ConnectionError as e:
        return {"error": str(e)}
    ok = st in (200, 201, 204)
    return (res if res is not None else {"ok": True}) if ok else _err_msg(st, res, what)


@mcp.tool
def gns3_events_url(project_id: Optional[str] = None, project_name: Optional[str] = None) -> Any:
    """URL del stream WebSocket de notificaciones, global o de un proyecto.

    La URL no lleva credenciales. Para suscribirse manualmente, usa
    `websockets.connect(url, additional_headers={"Authorization": "Basic <base64 usuario:contraseña>"})`
    y decodifica cada mensaje como JSON. `gns3_events(action="listen")` hace ambas cosas
    con la configuración local y un timeout estricto.
    """
    pid = None
    if project_id or project_name:
        pid, _ = _resolve_project(project_id, project_name)
        if not pid:
            return {"error": "proyecto no encontrado", "project_id": project_id,
                    "project_name": project_name}
    return {"url": _client().notifications_ws_url(pid), "note": "Suscríbete con websockets.connect; "
            "cada mensaje es JSON. Para autenticación HTTP Basic usa additional_headers con "
            "Authorization: Basic <base64 usuario:contraseña>, sin poner secretos en la URL."}


async def _listen_notifications(url: str, seconds: float, auth: tuple[str, str]) -> dict:
    """Escucha eventos reales hasta que vence exactamente el plazo solicitado."""
    token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode("ascii")
    headers = {"Authorization": f"Basic {token}"}
    events: list[Any] = []
    timed_out = False
    error = None
    try:
        async with asyncio.timeout(seconds):
            async with websockets.connect(
                url, additional_headers=headers,
                open_timeout=seconds, close_timeout=seconds,
            ) as ws:
                while True:
                    message = await ws.recv()
                    if isinstance(message, bytes):
                        message = message.decode(errors="replace")
                    try:
                        events.append(json.loads(message))
                    except json.JSONDecodeError:
                        events.append(message)
    except TimeoutError:
        timed_out = True
    except (OSError, websockets.exceptions.WebSocketException) as e:
        error = str(e)
    out = {"url": url, "seconds": seconds, "events": events, "timed_out": timed_out}
    if error:
        out["error"] = error
    return out


@mcp.tool
def gns3_events(action: str = "url", seconds: float = 5) -> Any:
    """Notificaciones WebSocket: action=url|listen.

    listen devuelve los eventos JSON recibidos y termina como máximo en `seconds`.
    Usa la autenticación de la configuración local sin exponerla en la URL ni en la salida.
    """
    action = action.lower()
    if action not in ("url", "listen"):
        return {"error": f"acción desconocida: {action}", "valid": ["url", "listen"]}
    if action == "url":
        return gns3_events_url()
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return {"error": "seconds debe ser un número positivo"}
    if not 0 < seconds < float("inf"):
        return {"error": "seconds debe ser un número positivo"}
    info = gns3_events_url()
    if not isinstance(info, dict) or info.get("error"):
        return info
    c = _conf()
    auth = (c.get("user", ""), c.get("password", ""))
    return asyncio.run(_listen_notifications(info["url"], seconds, auth))


@mcp.tool
def gns3_notifications(
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
) -> Any:
    """Notificaciones del servidor o de un proyecto concreto."""
    pid = None
    if project_id or project_name:
        pid, _ = _resolve_project(project_id, project_name)
        if not pid:
            return {"error": "proyecto no encontrado", "project_id": project_id,
                    "project_name": project_name}
    try:
        st, res = _client().notifications(pid)
    except ConnectionError as e:
        return {"error": str(e)}
    return res if st == 200 else _err_msg(st, res, "obtener notificaciones")


@mcp.tool
def gns3_iou_license(
    action: str = "get",
    body: Optional[dict] = None,
    confirm: bool = False,
) -> Any:
    """Licencia IOU: action=get|set. Cambiarla exige `body` y `confirm=True`."""
    action = action.lower()
    if action not in ("get", "set"):
        return {"error": f"acción desconocida: {action}", "valid": ["get", "set"]}
    if action == "set":
        if not isinstance(body, dict):
            return {"error": "set exige body (dict)"}
        if not confirm:
            return {"error": "actualizar la licencia IOU exige confirm=True"}
    client = _client()
    try:
        st, res = client.iou_license() if action == "get" else client.iou_license_update(body)
    except ConnectionError as e:
        return {"error": str(e)}
    what = "obtener licencia IOU" if action == "get" else "actualizar licencia IOU"
    ok = st in (200, 201, 204)
    return (res if res is not None else {"ok": True}) if ok else _err_msg(st, res, what)


@mcp.tool
def gns3_server(action: str = "version", confirm: bool = False) -> Any:
    """Servidor: action=version|shutdown|reload|debug.

    shutdown, reload y debug exigen `confirm=True` porque cambian el estado del servidor.
    """
    action = action.lower()
    if action not in ("version", "shutdown", "reload", "debug"):
        return {"error": f"acción desconocida: {action}",
                "valid": ["version", "shutdown", "reload", "debug"]}
    if action != "version" and not confirm:
        return {"error": f"{action} del servidor exige confirm=True"}
    client = _client()
    try:
        if action == "version":
            return client.version()
        methods = {"shutdown": client.server_shutdown, "reload": client.server_reload,
                   "debug": client.server_debug}
        st, res = methods[action]()
    except (ConnectionError, RuntimeError) as e:
        return {"error": str(e)}
    ok = st in (200, 201, 204)
    return (res if res is not None else {"ok": True}) if ok else _err_msg(st, res, action)


@mcp.tool
def gns3_emulator(
    action: str = "qemu-capabilities",
    port: Optional[int] = None,
    body: Optional[dict] = None,
    confirm: bool = False,
) -> Any:
    """Emuladores y red local: action=qemu-binaries|qemu-capabilities|docker-images|interfaces|ports|udp|img-binaries|img-config|virtualbox-vms|vmware-vms|vmware-vmnet.

    udp reserva un puerto UDP y exige `port`. img-config crea una imagen qemu-img
    con `body` o la actualiza sin `body`; vmware-vmnet crea una interfaz. img-config
    y vmware-vmnet exigen `confirm=True`.
    """
    methods = {
        "qemu-binaries": "qemu_binaries", "qemu-capabilities": "qemu_capabilities",
        "docker-images": "docker_images", "interfaces": "network_interfaces",
        "ports": "network_ports", "img-binaries": "qemu_img_binaries",
        "virtualbox-vms": "virtualbox_vms", "vmware-vms": "vmware_vms",
    }
    action = action.lower()
    valid = list(methods) + ["udp", "img-config", "vmware-vmnet"]
    if action not in valid:
        return {"error": f"acción desconocida: {action}", "valid": valid}
    if action == "udp" and (port is None or not 1 <= port <= 65535):
        return {"error": "udp exige port entre 1 y 65535"}
    if body is not None and not isinstance(body, dict):
        return {"error": "body debe ser un dict"}
    if action == "img-config" and not confirm:
        return {"error": "img-config exige confirm=True"}
    if action == "vmware-vmnet" and not confirm:
        return {"error": "vmware-vmnet exige confirm=True"}
    client = _client()
    try:
        if action == "udp":
            st, res = client.udp_port(port)
        elif action == "img-config":
            st, res = client.qemu_img_config(body)
        elif action == "vmware-vmnet":
            st, res = client.vmware_vmnet(body)
        else:
            st, res = getattr(client, methods[action])()
    except ConnectionError as e:
        return {"error": str(e)}
    ok = st in (200, 201, 204)
    return (res if res is not None else {"ok": True}) if ok else _api_error(st, res, action)


# ══════════════════════════════════════════════════════════════════════════════
# Resources y prompts: contexto del lab sin llamadas extra.
# ══════════════════════════════════════════════════════════════════════════════
def _resource_json(data: Any) -> str:
    """JSON legible para MCP; las resources nunca imprimen."""
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)


def _resource_project(project: str) -> tuple[Optional[dict], Optional[dict]]:
    """Resuelve por id exacto o nombre exacto, sin elegir entre duplicados."""
    projs = _projects()
    if not isinstance(projs, list):
        detail = projs.get("error", "respuesta no válida") if isinstance(projs, dict) else "respuesta no válida"
        return None, {"error": f"no se pudieron listar los proyectos: {detail}"}
    available = sorted(str(p.get("name") or p.get("project_id") or "") for p in projs)
    by_id = [p for p in projs if p.get("project_id") == project]
    if len(by_id) == 1:
        return by_id[0], None
    hits = [p for p in projs if str(p.get("name", "")).casefold() == project.casefold()]
    if len(hits) == 1:
        return hits[0], None
    names = ", ".join(available) or "(ninguno)"
    if not hits:
        error = f"proyecto no encontrado: {project}. Nombres disponibles: {names}"
    else:
        error = f"'{project}' es ambiguo: hay {len(hits)} proyectos con ese nombre. Nombres disponibles: {names}"
    return None, {"error": error, "available_projects": available}


@mcp.resource("gns3://status", mime_type="application/json")
def gns3_resource_status() -> str:
    """Versión, computes y estado actual del servidor GNS3."""
    return _resource_json(gns3_status())


@mcp.resource("gns3://projects", mime_type="application/json")
def gns3_resource_projects() -> str:
    """Proyectos del servidor con id, nombre y estado."""
    projs = gns3_projects(action="list")
    if isinstance(projs, list):
        projs = [{"project_id": p.get("project_id"), "name": p.get("name"),
                  "status": p.get("status")} for p in projs]
    return _resource_json(projs)


@mcp.resource("gns3://templates", mime_type="application/json")
def gns3_resource_templates() -> str:
    """Plantillas del servidor con id, tipo y nombre."""
    tpls = gns3_templates()
    if isinstance(tpls, list):
        tpls = [{"template_id": t.get("template_id"), "type": t.get("type"),
                 "name": t.get("name")} for t in tpls]
    return _resource_json(tpls)


@mcp.resource("gns3://project/{project}/topology", mime_type="application/json")
def gns3_resource_project_topology(project: str) -> str:
    """Nodos y enlaces de un proyecto, sin abrirlo ni modificar su estado."""
    proj, err = _resource_project(project)
    if err:
        return _resource_json(err)
    pid = proj["project_id"]
    nodes = _api("GET", f"/v2/projects/{pid}/nodes")
    if not isinstance(nodes, list):
        return _resource_json({"error": f"no se pudieron leer los nodos de {proj.get('name')}",
                               "detail": nodes})
    links = _api("GET", f"/v2/projects/{pid}/links")
    if not isinstance(links, list):
        return _resource_json({"error": f"no se pudieron leer los enlaces de {proj.get('name')}",
                               "detail": links})
    names = {n.get("node_id"): n.get("name") for n in nodes}
    return _resource_json({
        "project": {"project_id": pid, "name": proj.get("name"), "status": proj.get("status")},
        "nodes": [{"name": n.get("name"), "type": n.get("node_type"),
                   "status": n.get("status"), "console": n.get("console")} for n in nodes],
        "links": [{"link_id": link.get("link_id"),
                   "ends": [{"node": names.get(end.get("node_id"), end.get("node_id")),
                             "adapter": end.get("adapter_number"),
                             "port": end.get("port_number")} for end in link.get("nodes", [])]}
                  for link in links],
    })


@mcp.prompt(name="gns3-diagnostico", description="Guion para diagnosticar un lab GNS3 sin VNC.")
def gns3_diagnostico(proyecto: str) -> str:
    return f"""Diagnostica el proyecto GNS3 «{proyecto}» sin usar VNC y sin inventar resultados.

1. Ejecuta `gns3lab doctor` y revisa versión, computes, proyecto y hallazgos reales.
2. Lee `gns3://status` y `gns3://projects`. Confirma que «{proyecto}» existe y está abierto.
   Si el nombre es ambiguo, pide el project_id; no elijas un proyecto a ciegas.
3. Lee `gns3://project/<proyecto>/topology`, sustituyendo <proyecto> por el nombre o id
   codificado como URI. Compara la topologia (nodos, estados, consolas y enlaces) con el
   diagnóstico; no descarte un nodo por no aparecer en `status`.
4. Para cada nodo relevante:
   - Consola telnet: usa `gns3_exec` con `project_name` y comandos de solo lectura adecuados
     al sistema (por ejemplo, estado de interfaces, rutas y vecinos). Fija `expect` cuando
     conozcas el prompt; si no, deja que corte por quietud (`idle`), no por sleeps fijos.
   - Pantalla gráfica/QEMU: usa `gns3_monitor(action="text", scale=2, psm=4)` para leer la
     pantalla por OCR; para menús, emplea `action="key"` (`ret`, no `enter`) o `action="type"`; pide `shot` sólo si hace
     falta conservar una captura. El VNC es el último recurso.
5. Verifica conectividad de extremo a extremo con ping desde los clientes hacia su gateway
   y los destinos requeridos. Exige una salida real; un 200 de la API no basta. Comprueba
   porcentaje de pérdida, rutas, VLAN y NAT cuando formen parte del escenario.
6. Resume servidor, proyecto, nodos comprobados, evidencia observada, fallos literales y
   siguiente acción concreta. No incluyas credenciales."""


@mcp.prompt(name="gns3-examen", description="Guion para montar, verificar y portar el lab del examen.")
def gns3_examen(servidor: str = "clase") -> str:
    return f"""Monta y entrega el lab del examen en el servidor «{servidor}».

1. Consulta `~/GNS3/CHULETA.md` como referencia local del escenario. No copies ni reproduzcas
   sus credenciales en prompts, recursos, notas, logs ni respuestas.
2. Comprueba el servidor con `gns3lab --server {servidor} servers` y `doctor`. Lee resources
   de proyectos y plantillas si el MCP está conectado a ese servidor; no supongas que el
   servidor por defecto del MCP coincide con «{servidor}».
3. Abre y arranca el proyecto con `gns3lab --server {servidor} up <proyecto>`; confirma el
   estado real de cada nodo. Informa de cualquier cambio de estado fuera de la sesión.
4. Asigna interfaces según el enunciado y la topología. En pfSense con em0/em1 usa adaptadores
   e1000; incluye `port_number` en todos los `ports_mapping`. En ethernet_switch todos los
   puertos están en adapter 0. Valida cada enlace antes de crearlo.
5. Configura VLANs y direccionamiento por consola telnet (`gns3_exec`), respetando puertos
   access/trunk del switch y las interfaces del router. Lee primero la pantalla; en QEMU usa
   `gns3_monitor(action="text", scale=2, psm=4)` y teclas HMP (`ret`, `shift-<tecla>`), no VNC.
6. Procedimiento para verificar el laboratorio: `gns3lab --server {servidor} doctor <proyecto>`,
   estados, rutas, VLAN, NAT y ping entre clientes, gateway y destinos con 0% de pérdida. Pega
   la evidencia real; no des un resultado por bueno sin salida observada.
7. Instrucciones para portar el proyecto con `gns3lab --server {servidor} port --from local <proyecto>
   --name <nombre-destino> --start` cuando el origen sea local y el destino sea «{servidor}».
   Confirma antes el destino para no sobrescribir; el port puede parar y rearrancar nodos del
   origen. Repite doctor, topología y ping en el destino antes de darlo por terminado.
8. Entrega un resumen con proyecto origen/destino, interfaces, VLANs, pruebas y incidencias.
   No incluyas secretos ni rutas de otros usuarios."""


if __name__ == "__main__":
    mcp.run()
