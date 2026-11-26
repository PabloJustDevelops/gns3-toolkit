#!/usr/bin/env python3
"""gns3core — núcleo compartido por el MCP `gns3` y la CLI `gns3lab`.

Tres piezas, en orden de utilidad cuando algo se rompe:

1. `Client`   — API REST v2 de GNS3 2.2, con resolución de proyecto y nodo.
2. `Console`  — consola telnet de un nodo leída **por prompt/quietud**, con manejo de
                `--More--`, `[y/n]`, `Password:` y espera a que el nodo dé shell.
3. `QemuMonitor` — canal HMP (`-monitor tcp`): `sendkey`, `screendump`, `system_reset`.
                `screendump` devuelve un PPM con nombre .png; aquí se convierte a PNG
                real y se pasa por `tesseract`, que es la vía fiable para leer un menú
                sin depender del framebuffer VNC (que pierde y corrompe teclas).

Regla de oro: el VNC solo para instaladores interactivos con ratón. Todo lo demás va
por consola telnet (`Console`) o por el monitor (`QemuMonitor`).
"""
from __future__ import annotations

import base64
import fnmatch
import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

GNS3_CONF = Path.home() / ".config/GNS3/2.2/gns3_server.conf"
LAB_CONF = Path.home() / ".config/gns3lab/config.json"

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[()][A-Z0-9]")


# ─────────────────────────── configuración de servidores ───────────────────────────
def local_auth() -> Optional[tuple[str, str]]:
    """Usuario/contraseña del servidor local, del conf de la GUI de GNS3."""
    if not GNS3_CONF.exists():
        return None
    txt = GNS3_CONF.read_text(errors="replace")
    user = re.search(r"^user\s*=\s*(\S+)", txt, re.M)
    pwd = re.search(r"^password\s*=\s*(\S+)", txt, re.M)
    if user and pwd:
        return user.group(1), pwd.group(1)
    return None


def lab_conf() -> dict:
    default = {
        "servers": {
            "local": {"url": "http://127.0.0.1:3080", "auth": "from-gns3-conf"},
            "clase": {"url": "http://192.168.71.250:80", "auth": None, "matcher": "Pablo Rodriguez"},
        },
        "default_server": "local",
    }
    if LAB_CONF.exists():
        try:
            return json.loads(LAB_CONF.read_text())
        except json.JSONDecodeError:
            return default
    return default


def server_config(name: str = "local", conf: Optional[dict] = None) -> dict:
    conf = conf or lab_conf()
    servers = conf.get("servers", {})
    if name not in servers:
        raise SystemExit(f"servidor '{name}' no configurado. Disponibles: {', '.join(servers)}")
    s = dict(servers[name])
    s.setdefault("name", name)
    s["url"] = s["url"].rstrip("/")
    s["auth"] = local_auth() if s.get("auth") == "from-gns3-conf" else None
    return s


def clean(text: str) -> str:
    text = ANSI_RE.sub("", text)
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    # negociación telnet (IAC FF FB 01...) llega como U+FFFD al decodificar
    return text.replace("\ufffd", "")


# ───────────────────────────────── cliente REST ─────────────────────────────────
class Client:
    """Cliente mínimo de la API v2 (2.2.x). Devuelve (status, body)."""

    def __init__(self, url: str = "http://127.0.0.1:3080",
                 auth: Optional[tuple[str, str]] = None, matcher: Optional[str] = None,
                 name: str = "local"):
        self.url = url.rstrip("/")
        self.auth = auth
        self.matcher = matcher
        self.name = name

    @classmethod
    def from_name(cls, name: str = "local", conf: Optional[dict] = None) -> "Client":
        s = server_config(name, conf)
        return cls(s["url"], s.get("auth"), s.get("matcher"), s["name"])

    # transporte
    def req(self, method: str, path: str, data: Optional[bytes] = None,
            ctype: str = "application/json", timeout: float = 60,
            raw: bool = False) -> tuple[int, Any]:
        headers = {}
        if data is not None:
            headers["Content-Type"] = ctype
        if self.auth:
            tok = base64.b64encode(f"{self.auth[0]}:{self.auth[1]}".encode()).decode()
            headers["Authorization"] = "Basic " + tok
        req = urllib.request.Request(self.url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                return r.status, (body if raw else self._json(body))
        except urllib.error.HTTPError as e:
            body = e.read()
            return e.code, (body if raw else self._json(body))
        except urllib.error.URLError as e:
            raise ConnectionError(f"no puedo conectar con {self.url}: {e.reason}") from e

    def _json(self, body: bytes):
        if not body:
            return None
        try:
            return json.loads(body.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return body.decode(errors="replace")

    def get(self, path, **kw):
        return self.req("GET", path, **kw)

    def post(self, path, payload=None, **kw):
        data = b""
        if payload is not None:
            data = json.dumps(payload).encode()
        return self.req("POST", path, data=data, **kw)

    def put(self, path, payload: dict, **kw):
        return self.req("PUT", path, data=json.dumps(payload).encode(), **kw)

    def delete(self, path, **kw):
        return self.req("DELETE", path, **kw)

    def json_or_die(self, path: str, what: str, **kw):
        st, body = self.get(path, **kw)
        if st != 200:
            raise RuntimeError(f"{what}: [{st}] {body}")
        return body

    def alive(self) -> bool:
        try:
            st, body = self.get("/v2/version", timeout=6)
            return st == 200 and isinstance(body, dict)
        except (ConnectionError, OSError):
            return False

    # consultas
    def version(self) -> dict:
        return self.json_or_die("/v2/version", "version")

    def projects(self) -> list[dict]:
        body = self.json_or_die("/v2/projects", "proyectos")
        return body if isinstance(body, list) else []

    def nodes(self, pid: str) -> list[dict]:
        body = self.json_or_die(f"/v2/projects/{pid}/nodes", f"nodos de {pid[:8]}")
        return body if isinstance(body, list) else []

    def links(self, pid: str) -> list[dict]:
        st, body = self.get(f"/v2/projects/{pid}/links")
        return body if st == 200 and isinstance(body, list) else []

    def templates(self) -> list[dict]:
        st, body = self.get("/v2/templates")
        return body if st == 200 and isinstance(body, list) else []

    def qemu_images(self) -> list[dict]:
        st, body = self.get("/v2/computes/local/qemu/images")
        return body if st == 200 and isinstance(body, list) else []

    def resolve_project(self, needle: Optional[str]) -> dict:
        """Proyecto por nombre parcial o id. Sin needle: el único abierto."""
        projects = self.projects()
        if not projects:
            raise SystemExit(f"{self.name}: el servidor no tiene proyectos")
        if needle:
            low = needle.lower()
            hits = [p for p in projects
                    if low in p["name"].lower() or p["project_id"].startswith(needle)]
            if not hits:
                raise SystemExit(f"ningún proyecto coincide con '{needle}'")
            if len(hits) > 1:
                nombres = ", ".join(f"{p['name']} ({p['project_id'][:8]})" for p in hits)
                raise SystemExit(f"'{needle}' es ambiguo: {nombres}")
            return hits[0]
        opened = [p for p in projects if p.get("status") == "opened"]
        if len(opened) == 1:
            return opened[0]
        if len(opened) > 1:
            if self.matcher:
                hits = [p for p in opened if re.search(self.matcher, p["name"], re.I)]
                if len(hits) == 1:
                    return hits[0]
            nombres = ", ".join(f"{p['name']} ({p['project_id'][:8]})" for p in opened)
            raise SystemExit(f"hay varios abiertos, di cuál: {nombres}")
        if len(projects) == 1:
            return projects[0]
        nombres = ", ".join(f"{p['name']} ({p['project_id'][:8]})" for p in projects)
        raise SystemExit(f"ninguno abierto; di cuál: {nombres}")

    def ensure_open(self, pid: str) -> None:
        st, info = self.get(f"/v2/projects/{pid}")
        if st != 200 or not isinstance(info, dict):
            raise RuntimeError(f"proyecto {pid[:8]}: [{st}] {info}")
        if info.get("status") == "opened":
            return
        st, res = self.post(f"/v2/projects/{pid}/open", timeout=300)
        if st not in (200, 201):
            # carrera de arranque conocida: libvirt activa las redes después del 1er intento
            time.sleep(3)
            st, res = self.post(f"/v2/projects/{pid}/open", timeout=300)
            if st not in (200, 201):
                msg = res.get("message") if isinstance(res, dict) else res
                raise RuntimeError(f"no abre el proyecto: [{st}] {msg}")

    def find_node(self, pid: str, pattern: str) -> dict:
        nodes = self.nodes(pid)
        hit = match_nodes(nodes, pattern)
        if not hit:
            raise SystemExit(f"nodo no encontrado: {pattern!r}. Hay: {', '.join(n['name'] for n in nodes)}")
        return hit[0]

    def node_detail(self, pid: str, nid: str) -> dict:
        return self.json_or_die(f"/v2/projects/{pid}/nodes/{nid}", f"nodo {nid[:8]}")


    # ── superficie v2 ampliada (paridad CLI/MCP) ──────────────────────────────
    def computes(self) -> list[dict]:
        st, body = self.get("/v2/computes")
        return body if st == 200 and isinstance(body, list) else []

    def compute(self, cid: str = "local") -> Optional[dict]:
        st, body = self.get(f"/v2/computes/{cid}")
        return body if st == 200 and isinstance(body, dict) else None

    def statistics(self) -> list[dict]:
        st, body = self.get("/v2/statistics")
        return body if st == 200 and isinstance(body, list) else []

    def symbols(self) -> list[dict]:
        st, body = self.get("/v2/symbols")
        return body if st == 200 and isinstance(body, list) else []

    def appliances(self) -> list[dict]:
        st, body = self.get("/v2/appliances")
        return body if st == 200 and isinstance(body, list) else []

    def images(self, emulator: str = "qemu") -> list[dict]:
        emulator = emulator.removesuffix("/images")
        st, body = self.get(f"/v2/computes/local/{emulator}/images")
        return body if st == 200 and isinstance(body, list) else []

    def project_get(self, pid: str) -> dict:
        return self.json_or_die(f"/v2/projects/{pid}", f"proyecto {pid[:8]}")

    def project_close(self, pid: str) -> tuple[int, Any]:
        return self.post(f"/v2/projects/{pid}/close", timeout=180)

    def project_delete(self, pid: str) -> tuple[int, Any]:
        return self.delete(f"/v2/projects/{pid}", timeout=180)

    def template_get(self, tid: str) -> tuple[int, Any]:
        return self.get(f"/v2/templates/{tid}")

    def template_update(self, tid: str, body: dict) -> tuple[int, Any]:
        return self.put(f"/v2/templates/{tid}", body, timeout=120)

    def template_delete(self, tid: str) -> tuple[int, Any]:
        return self.delete(f"/v2/templates/{tid}", timeout=120)

    def node_action(self, pid: str, nid: str, action: str, timeout: float = 180) -> tuple[int, Any]:
        """start|stop|reload|suspend|resume|pause|unpause sobre un nodo."""
        if action not in ("start", "stop", "reload", "suspend", "resume", "pause", "unpause"):
            raise ValueError(f"acción de nodo desconocida: {action}")
        return self.post(f"/v2/projects/{pid}/nodes/{nid}/{action}", timeout=timeout)

    def nodes_action(self, pid: str, action: str, timeout: float = 300) -> tuple[int, Any]:
        """Acción masiva del proyecto (GUI: botones Start/Stop de toda la topología)."""
        if action not in ("start", "stop", "suspend", "reload"):
            raise ValueError(f"acción masiva desconocida: {action}")
        return self.post(f"/v2/projects/{pid}/nodes/{action}", timeout=timeout)

    def nodes_console_reset(self, pid: str) -> tuple[int, Any]:
        return self.post(f"/v2/projects/{pid}/nodes/console/reset", timeout=120)

    def _emulator_for(self, pid: str, nid: str) -> str:
        """Tipo de compute del nodo (`qemu`, `vpcs`, `docker`…) para rutas `/computes/local/…`."""
        detail = self.node_detail(pid, nid)
        return str(detail.get("node_type") or "qemu") if isinstance(detail, dict) else "qemu"

    def port_nio(self, pid: str, nid: str, adapter: int, port: int,
                 body: Optional[dict] = None, emulator: Optional[str] = None,
                 delete: bool = False) -> tuple[int, Any]:
        """NIO de un puerto: la vía de enganche que señaló el REA de ubridge.

        Estas rutas seSirven en el compute, no en el controller; el proxy las reenvía.
        Un `500` del compute se devuelve tal cual: es información real, no se disfraza.
        """
        emu = emulator or self._emulator_for(pid, nid)
        path = (f"/v2/computes/local/projects/{pid}/{emu}/nodes/{nid}"
                f"/adapters/{adapter}/ports/{port}/nio")
        if delete:
            return self.delete(path, timeout=120)
        return self.put(path, body or {}, timeout=120) if body is not None else self.get(path)

    def port_capture(self, pid: str, nid: str, adapter: int, port: int, action: str,
                     file_name: Optional[str] = None,
                     emulator: Optional[str] = None) -> tuple[int, Any]:
        """Captura por puerto (`start_capture|stop_capture|pcap`), distinta de la de enlace."""
        if action not in ("start_capture", "stop_capture", "pcap"):
            raise ValueError(f"acción de captura de puerto desconocida: {action}")
        emu = emulator or self._emulator_for(pid, nid)
        base = (f"/v2/computes/local/projects/{pid}/{emu}/nodes/{nid}"
                f"/adapters/{adapter}/ports/{port}")
        if action == "pcap":
            return self.get(f"{base}/pcap", raw=True, timeout=180)
        body = {"capture_file_name": file_name or f"port-{nid[:8]}-{adapter}-{port}.pcap"}
        if action == "start_capture":
            body["data_link_type"] = "DLT_EN10MB"
        return self.post(f"{base}/{action}", body, timeout=120)

    def qemu_img_binaries(self) -> tuple[int, Any]:
        return self.get("/v2/computes/local/qemu/img-binaries")

    def qemu_img_config(self, body: Optional[dict] = None) -> tuple[int, Any]:
        return self.post("/v2/computes/local/qemu/img", body, timeout=180) if body is not None \
            else self.put("/v2/computes/local/qemu/img", {}, timeout=180)

    def virtualbox_vms(self) -> tuple[int, Any]:
        return self.get("/v2/computes/local/virtualbox/vms")

    def vmware_vms(self) -> tuple[int, Any]:
        return self.get("/v2/computes/local/vmware/vms")

    def vmware_vmnet(self, body: Optional[dict] = None) -> tuple[int, Any]:
        return self.post("/v2/computes/local/vmware/nodes/interfaces/vmnet",
                         body or {}, timeout=120)

    def notifications_ws_url(self, pid: Optional[str] = None) -> str:
        base = self.url.replace("http://", "ws://").replace("https://", "wss://")
        return f"{base}/v2/projects/{pid}/notifications/ws" if pid else f"{base}/v2/notifications/ws"

    def v1_version(self) -> tuple[int, Any]:
        return self.get("/v1/version")

    def node_command_line(self, pid: str, nid: str) -> str:
        detail = self.node_detail(pid, nid)
        return detail.get("command_line", "") if isinstance(detail, dict) else ""

    def link_get(self, pid: str, lid: str) -> tuple[int, Any]:
        """Detalle de un enlace: extremos, filtros y estado de captura."""
        return self.get(f"/v2/projects/{pid}/links/{lid}")

    def link_update(self, pid: str, lid: str, body: dict) -> tuple[int, Any]:
        return self.put(f"/v2/projects/{pid}/links/{lid}", body, timeout=120)

    def link_delete(self, pid: str, lid: str) -> tuple[int, Any]:
        return self.delete(f"/v2/projects/{pid}/links/{lid}", timeout=120)

    def link_capture(self, pid: str, lid: str, action: str, file_name: Optional[str] = None) -> tuple[int, Any]:
        """start|stop|pcap de la captura de un enlace."""
        if action == "start":
            return self.post(f"/v2/projects/{pid}/links/{lid}/start_capture", {
                "data_link_type": "DLT_EN10MB",
                "capture_file_name": file_name or f"capture-{lid[:8]}.pcap",
            }, timeout=120)
        if action == "stop":
            return self.post(f"/v2/projects/{pid}/links/{lid}/stop_capture", timeout=120)
        if action == "pcap":
            return self.get(f"/v2/projects/{pid}/links/{lid}/pcap", raw=True, timeout=180)
        raise ValueError(f"acción de captura desconocida: {action}")

    def drawing_get(self, pid: str, did: str) -> tuple[int, Any]:
        """Detalle de un dibujo: posición, rotación y SVG completo."""
        return self.get(f"/v2/projects/{pid}/drawings/{did}")

    def drawing_update(self, pid: str, did: str, body: dict) -> tuple[int, Any]:
        return self.put(f"/v2/projects/{pid}/drawings/{did}", body, timeout=120)

    def drawing_delete(self, pid: str, did: str) -> tuple[int, Any]:
        return self.delete(f"/v2/projects/{pid}/drawings/{did}", timeout=120)

    def snapshots(self, pid: str) -> list[dict]:
        st, body = self.get(f"/v2/projects/{pid}/snapshots")
        return body if st == 200 and isinstance(body, list) else []

    def snapshot_create(self, pid: str, name: str) -> tuple[int, Any]:
        return self.post(f"/v2/projects/{pid}/snapshots", {"name": name}, timeout=300)

    def snapshot_restore(self, pid: str, sid: str) -> tuple[int, Any]:
        return self.post(f"/v2/projects/{pid}/snapshots/{sid}/restore", timeout=300)

    def snapshot_delete(self, pid: str, sid: str) -> tuple[int, Any]:
        return self.delete(f"/v2/projects/{pid}/snapshots/{sid}", timeout=180)

    def drawings(self, pid: str) -> list[dict]:
        st, body = self.get(f"/v2/projects/{pid}/drawings")
        return body if st == 200 and isinstance(body, list) else []

    def drawing_create(self, pid: str, body: dict) -> tuple[int, Any]:
        return self.post(f"/v2/projects/{pid}/drawings", body)

    def compute_write_file(self, cid: str, emulator: str, filename: str,
                           data: bytes, ctype: str = "application/octet-stream") -> tuple[int, Any]:
        return self.req("POST", f"/v2/computes/{cid}/{emulator}/images/{filename}",
                        data=data, ctype=ctype, timeout=1800)


    # ── GUI operativa portada a la API v2 (rutas leídas de gns3server) ──────────
    def node_resize_disk(self, pid: str, nid: str, size: int,
                         drive: str = "hda") -> tuple[int, Any]:
        """Equivale a «Resize disk» del diálogo de propiedades QEMU.

        GNS3 2.2 exige `{"drive_name", "extend"}` con `extend` en **MiB**; el
        antiguo `hda_disk_size` lo rechaza el schema (400) y el disco no crece.
        """
        if drive not in ("hda", "hdb", "hdc", "hdd"):
            raise ValueError(f"drive no válido: {drive!r} (hda, hdb, hdc o hdd)")
        return self.post(f"/v2/projects/{pid}/nodes/{nid}/resize_disk",
                         {"drive_name": drive, "extend": int(size)}, timeout=300)

    def console_reset(self, pid: str, nid: str) -> tuple[int, Any]:
        return self.post(f"/v2/projects/{pid}/nodes/{nid}/console/reset", timeout=60)

    def console_ws_url(self, pid: str, nid: str) -> str:
        detail = self.node_detail(pid, nid)
        if not isinstance(detail, dict):
            return ""
        return str(detail.get("console_url") or
                   (f"ws://127.0.0.1:3080/v2/projects/{pid}/nodes/{nid}/console/ws"
                    if detail.get("console_type") in ("telnet", "vnc") else ""))

    def node_links(self, pid: str, nid: str) -> list[dict]:
        st, body = self.get(f"/v2/projects/{pid}/nodes/{nid}/links")
        return body if st == 200 and isinstance(body, list) else []

    def node_idlepc(self, pid: str, nid: str, proposals: bool = False) -> tuple[int, Any]:
        action = "idlepc_proposals" if proposals else "auto_idlepc"
        return self.get(f"/v2/projects/{pid}/nodes/{nid}/dynamips/{action}", timeout=120)

    def link_available_filters(self, pid: str, lid: str) -> tuple[int, Any]:
        return self.get(f"/v2/projects/{pid}/links/{lid}/available_filters")

    def project_stats(self, pid: str) -> tuple[int, Any]:
        return self.get(f"/v2/projects/{pid}/stats")

    def project_duplicate(self, pid: str, name: Optional[str] = None) -> tuple[int, Any]:
        body = {"name": name} if name else {}
        st, res = self.post(f"/v2/projects/{pid}/duplicate", body, timeout=600)
        if st in (200, 201) and name and isinstance(res, dict) and res.get("name") != name:
            new_id = res.get("project_id")
            if new_id:
                self.put(f"/v2/projects/{new_id}", {"name": name})
                res["name"] = name
        return st, res

    def project_load(self, path: str) -> tuple[int, Any]:
        return self.post("/v2/projects/load", {"path": path}, timeout=300)

    def project_file_read(self, pid: str, path: str) -> Any:
        st, body = self.get(f"/v2/projects/{pid}/files/{path.lstrip('/')}", raw=True)
        if st != 200 or not isinstance(body, bytes):
            return {"error": f"HTTP {st}"}
        return body.decode(errors="replace")

    def project_file_write(self, pid: str, path: str, content: str) -> tuple[int, Any]:
        return self.req("POST", f"/v2/projects/{pid}/files/{path.lstrip('/')}",
                        data=content.encode(), ctype="text/plain", timeout=60)

    def compute_create(self, body: dict) -> tuple[int, Any]:
        return self.post("/v2/computes", body, timeout=120)

    def compute_update(self, cid: str, body: dict) -> tuple[int, Any]:
        return self.put(f"/v2/computes/{cid}", body, timeout=120)

    def compute_delete(self, cid: str) -> tuple[int, Any]:
        return self.delete(f"/v2/computes/{cid}", timeout=120)

    def compute_ports(self, cid: str) -> tuple[int, Any]:
        return self.get(f"/v2/computes/{cid}/ports")

    def compute_auto_idlepc(self, cid: str) -> tuple[int, Any]:
        return self.post(f"/v2/computes/{cid}/auto_idlepc", timeout=120)

    def compute_action(self, cid: str, emulator: str, action: str,
                       body: Optional[dict] = None) -> tuple[int, Any]:
        """Ruta genérica `/computes/{id}/{emulator}/{action}` (GUI: img, binaries…)."""
        path = f"/v2/computes/{cid}/{emulator}/{action}"
        return self.post(path, body, timeout=300) if body is not None else self.get(path)

    def gns3vm(self) -> tuple[int, Any]:
        return self.get("/v2/gns3vm")

    def gns3vm_update(self, body: dict) -> tuple[int, Any]:
        return self.put("/v2/gns3vm", body, timeout=120)

    def gns3vm_engines(self) -> tuple[int, Any]:
        return self.get("/v2/gns3vm/engines")

    def gns3vm_vms(self, engine: str) -> tuple[int, Any]:
        return self.get(f"/v2/gns3vm/engines/{engine}/vms")

    def notifications(self, pid: Optional[str] = None) -> tuple[int, Any]:
        path = f"/v2/projects/{pid}/notifications" if pid else "/v2/notifications"
        return self.get(path)

    def template_duplicate(self, tid: str, name: Optional[str] = None) -> tuple[int, Any]:
        return self.post(f"/v2/templates/{tid}/duplicate",
                         {"name": name} if name else {}, timeout=180)

    def template_base_configs(self) -> tuple[int, Any]:
        return self.get("/v2/templates/base-configs")

    def template_base_config(self, tid: str, filename: str, content: Optional[str] = None) -> Any:
        path = f"/v2/templates/{tid}/base-config/{filename}"
        if content is None:
            st, body = self.get(path, raw=True)
            return body.decode(errors="replace") if st == 200 and isinstance(body, bytes) else {"error": f"HTTP {st}"}
        return self.put(path, {"content": content}, timeout=60)

    def symbol_dimensions(self, symbol_id: str) -> tuple[int, Any]:
        return self.get(f"/v2/symbols/{symbol_id}/dimensions")

    def symbol_raw(self, symbol_id: str) -> tuple[int, Any]:
        return self.get(f"/v2/symbols/{symbol_id}/raw", raw=True)

    def symbol_raw_upload(self, symbol_id: str, data: bytes) -> tuple[int, Any]:
        return self.req("POST", f"/v2/symbols/{symbol_id}/raw", data=data,
                        ctype="application/octet-stream", timeout=120)

    def default_symbols(self) -> tuple[int, Any]:
        return self.get("/v2/default_symbols")

    def iou_license(self) -> tuple[int, Any]:
        return self.get("/v2/iou_license")

    def iou_license_update(self, body: dict) -> tuple[int, Any]:
        return self.put("/v2/iou_license", body, timeout=60)

    # Ojo: `shutdown` y `reload` paran el servidor. Solo en un entorno de prueba.
    def server_shutdown(self) -> tuple[int, Any]:
        return self.post("/v2/shutdown", timeout=60)

    def server_reload(self) -> tuple[int, Any]:
        return self.post("/v2/reload", timeout=60)

    def server_debug(self) -> tuple[int, Any]:
        return self.post("/v2/debug", timeout=60)

    def qemu_binaries(self) -> tuple[int, Any]:
        return self.get("/v2/computes/local/qemu/binaries")

    def qemu_capabilities(self) -> tuple[int, Any]:
        return self.get("/v2/computes/local/qemu/capabilities")

    def docker_images(self) -> tuple[int, Any]:
        return self.get("/v2/computes/local/docker/images")

    def network_interfaces(self) -> tuple[int, Any]:
        return self.get("/v2/computes/local/network/interfaces")

    def network_ports(self) -> tuple[int, Any]:
        return self.get("/v2/computes/local/network/ports")

    def udp_port(self, port: int) -> tuple[int, Any]:
        return self.post("/v2/computes/local/ports/udp", {"port": port}, timeout=60)


# Rutas de la API v2 cubiertas por este núcleo. La documentación usa este mapa
# para declarar la cobertura sin inventar endpoints.
API_V2_MAP: dict[str, tuple[str, ...]] = {
    "server": ("GET /v2/version",),
    "computes": ("GET /v2/computes", "GET /v2/computes/{id}", "GET /v2/statistics",
                 "GET /v2/computes/{id}/{emulator}/images",
                 "POST /v2/computes/{id}/{emulator}/images/{filename}"),
    "projects": ("GET/POST /v2/projects", "GET/PUT/DELETE /v2/projects/{id}",
                 "POST /v2/projects/{id}/open", "POST /v2/projects/{id}/close",
                 "GET /v2/projects/{id}/export", "POST /v2/projects/{id}/import"),
    "templates": ("GET /v2/templates", "GET/PUT/DELETE /v2/templates/{id}",
                  "POST /v2/projects/{id}/templates/{tid}", "GET /v2/appliances"),
    "nodes": ("GET/POST /v2/projects/{id}/nodes", "GET/PUT/DELETE /nodes/{nid}",
              "POST /nodes/{nid}/{start|stop|reload|suspend|duplicate}",
              "GET/POST /nodes/{nid}/files/{path}", "GET /v2/symbols"),
    "links": ("GET/POST /v2/projects/{id}/links", "GET/PUT/DELETE /links/{lid}",
              "POST /links/{lid}/{start_capture|stop_capture}", "GET /links/{lid}/pcap"),
    "drawings": ("GET/POST /v2/projects/{id}/drawings",
                 "GET/PUT/DELETE /drawings/{did}"),
    "snapshots": ("GET/POST /v2/projects/{id}/snapshots",
                  "POST /snapshots/{sid}/restore", "DELETE /snapshots/{sid}"),
    "symbols": ("GET /v2/symbols", "GET /symbols/{id}/dimensions",
                "GET/POST /symbols/{id}/raw", "GET /v2/default_symbols"),
    "gui_admin": ("GET/PUT /v2/gns3vm", "GET /gns3vm/engines", "GET /engines/{e}/vms",
                  "GET/PUT /v2/iou_license", "GET /v2/notifications",
                  "GET /projects/{id}/notifications", "POST /v2/shutdown",
                  "POST /v2/reload", "POST /v2/debug"),
    "emulators": ("GET /computes/local/qemu/binaries", "GET /qemu/capabilities",
                  "GET /computes/local/docker/images", "GET /network/interfaces",
                  "GET /network/ports", "POST /ports/udp",
                  "GET /nodes/{nid}/dynamips/auto_idlepc"),
    "nio_ports": ("GET/PUT/DELETE /computes/local/projects/{id}/{emu}/nodes/{nid}"
                  "/adapters/{a}/ports/{p}/nio",
                  "POST /computes/local/projects/{id}/{emu}/nodes/{nid}"
                  "/adapters/{a}/ports/{p}/{start_capture|stop_capture}",
                  "GET /computes/local/…/ports/{p}/pcap",
                  "POST /projects/{id}/nodes/{start|stop|suspend|reload}",
                  "POST /projects/{id}/nodes/console/reset",
                  "GET /computes/local/qemu/img-binaries", "POST/PUT /computes/local/qemu/img",
                  "GET /computes/local/{virtualbox|vmware}/vms",
                  "GET /{v1|v2}/version", "GET /notifications/ws"),
}


def match_nodes(nodes: list[dict], pattern: Optional[str]) -> list[dict]:
    if not pattern:
        return []
    if pattern in ("*", "all"):
        return list(nodes)
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


def node_file_read(client: "Client", pid: str, nid: str, path: str) -> Any:
    """Lee un fichero del directorio del nodo. Devuelve str o el error."""
    st, body = client.get(f"/v2/projects/{pid}/nodes/{nid}/files/{path.lstrip('/')}", raw=True)
    if st != 200 or not isinstance(body, bytes):
        return {"error": f"HTTP {st}", "detail": body if not isinstance(body, bytes) else body[:200]}
    return body.decode(errors="replace")


def node_file_write(client: "Client", pid: str, nid: str, path: str, content: str) -> dict:
    """Escribe un fichero en el directorio del nodo.

    El body va **en crudo**: mandar `{"content": "..."}` graba ese JSON tal cual en el
    fichero (un `startup.vpc` con JSON dentro no lo ejecuta VPCS).
    """
    st, body = client.req("POST", f"/v2/projects/{pid}/nodes/{nid}/files/{path.lstrip('/')}",
                          data=content.encode(), ctype="text/plain", timeout=60)
    return {"status": st, "ok": st in (200, 201, 204),
            "error": body if st >= 400 and isinstance(body, dict) else None}


def node_summary(n: dict) -> dict:
    return {
        "name": n.get("name"),
        "node_id": n.get("node_id"),
        "type": n.get("node_type"),
        "status": n.get("status"),
        "console": n.get("console"),
        "console_type": n.get("console_type"),
        "ports": [p.get("name") for p in (n.get("ports") or [])],
    }


# ─────────────────────────────── consola telnet ───────────────────────────────
MORE_RE = re.compile(r"--\s*\(?more\)?\s*--|--More--|\(q\)\s*quit", re.I)
ASK_RE = re.compile(r"\[y/n\]|\(y/n\)|\[confirm\]|\[yes/no\]|\(yes/no\)|are you sure", re.I)
PASS_RE = re.compile(r"(?:password|passphrase|contraseña)\s*:\s*$", re.I)
PROMPT_TAIL = re.compile(r"(?:^|\n)([^\n]{0,60}?[>#$%])\s*$")


class ConsoleError(RuntimeError):
    pass


class Console:
    """Consola telnet de nodo GNS3, leída por prompt o por quietud.

    Uso típico::

        with Console(host, port) as c:
            c.wait_ready()                      # espera a que haya shell
            print(c.run("show ip")["output"])

    No usa `sleep` fijo: lee hasta que la salida se queda quieta `idle` segundos o
    hasta que casa `expect`. Responde sola a la paginación (`--More--`) y a las
    confirmaciones (`[y/n]`), que es lo que deja colgada una sesión telnet.
    """

    def __init__(self, host: str, port: int, timeout: float = 10.0):
        self.host, self.port = host, int(port)
        self.sock = socket.create_connection((host, self.port), timeout=timeout)
        self.sock.settimeout(0.2)
        self.prompt: Optional[str] = None
        self.closed = False

    # -- ciclo de vida -------------------------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        self.closed = True
        try:
            self.sock.close()
        except OSError:
            pass

    # -- E/S ---------------------------------------------------------------
    def send(self, data: str):
        try:
            self.sock.sendall(data.encode())
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            self.closed = True
            raise ConsoleError(f"la consola se cerró al escribir: {e}") from e

    def _pump(self, seconds: float) -> str:
        """Lee durante `seconds` y devuelve el texto limpio recibido."""
        buf = b""
        end = time.time() + seconds
        while time.time() < end and not self.closed:
            try:
                chunk = self.sock.recv(65536)
                if not chunk:
                    self.closed = True
                    break
                buf += chunk
            except socket.timeout:
                continue
            except OSError:
                self.closed = True
                break
        return clean(buf.decode(errors="replace"))

    def drain(self, seconds: float = 0.8) -> str:
        return self._pump(seconds)

    def wake(self, seconds: float = 1.2) -> str:
        """Manda Enter y devuelve lo que salga. Despierta consolas dormidas."""
        self.send("\n")
        return self.drain(seconds)

    def wait_ready(self, timeout: float = 30.0, expect: Optional[str] = None,
                   grub_retries: int = 3) -> dict:
        """Espera a que el nodo dé shell.

        Devuelve ``{"ready": bool, "prompt": str|None, "output": str}``. Si aparece el
        menú de GRUB (disco a medio escribir) pulsa Enter, que es lo que lo resuelve.
        """
        deadline = time.time() + timeout
        text = self.wake(1.0)
        grub = 0
        while time.time() < deadline:
            text += self.drain(0.6)
            tail = text[-800:]
            if expect and re.search(expect, tail):
                self.prompt = expect
                return {"ready": True, "prompt": expect, "output": text}
            if "GNU GRUB" in tail and grub < grub_retries:
                self.send("\n")
                grub += 1
                time.sleep(1.5)
                continue
            m = PROMPT_TAIL.search(tail)
            if m:
                self.prompt = m.group(1).strip()
                return {"ready": True, "prompt": self.prompt, "output": text}
        return {"ready": False, "prompt": None, "output": text}

    def run(self, cmd: str, expect: Optional[str] = None, timeout: float = 20.0,
            idle: float = 0.9, more: bool = True, answers: Optional[list[str]] = None,
            password: Optional[str] = None, strip_echo: bool = True) -> dict:
        """Ejecuta un comando y devuelve ``{cmd, output, ok, ms, timed_out}``.

        - `expect`: regex que marca el fin (por defecto, quietud de `idle` segundos).
        - `answers`: respuestas para `[y/n]` en orden (por defecto `y`).
        - `password`: se envía cuando aparece un prompt de contraseña.
        """
        answers = list(answers or [])
        start = time.time()
        self.send(cmd + "\n")
        buf = ""
        last = time.time()
        timed_out = False
        more_hits = 0
        # Posición de `buf` hasta la que ya se contestó a una pregunta. Sin esto, un
        # `[y/n]` que sigue en pantalla se responde en bucle (18 respuestas medidas) y
        # el `continue` se comía el chequeo de timeout.
        answered_upto = 0
        while True:
            if time.time() - start > timeout:
                timed_out = True
                break
            if self.closed:
                break
            chunk = self._pump(0.25)
            now = time.time()
            if chunk:
                buf += chunk
                last = now
            tail = buf[-400:]
            fresh = buf[answered_upto:]
            if more and MORE_RE.search(fresh):
                self.send(" ")
                more_hits += 1
                answered_upto = len(buf)
                if more_hits > 200:
                    more = False
                continue
            if PASS_RE.search(fresh) and password is not None:
                self.send(password + "\n")
                password = None       # solo una vez
                answered_upto = len(buf)
                continue
            if ASK_RE.search(fresh):
                self.send((answers.pop(0) if answers else "y") + "\n")
                answered_upto = len(buf)
                continue
            if expect and re.search(expect, tail):
                break
            if not chunk and now - last >= idle:
                break
        ms = int((time.time() - start) * 1000)
        out = buf
        if strip_echo:
            first, _, rest = out.partition("\n")
            if first.strip().endswith(cmd.strip()[-20:]) or cmd.strip() in first:
                out = rest
        # quita el prompt final duplicado
        if self.prompt:
            out = re.sub(re.escape(self.prompt) + r"\s*$", "", out)
        return {"cmd": cmd, "output": out.strip("\n"), "ok": not timed_out,
                "timed_out": timed_out, "ms": ms, "more_pages": more_hits}

    def run_many(self, cmds: list[str], **kw) -> list[dict]:
        """Ejecuta en cadena compartiendo sesión: `set pcname`, `ip dhcp`, `show ip`."""
        expect = kw.pop("expect", None)
        res = []
        for c in cmds:
            r = self.run(c, expect=expect, **kw)
            res.append(r)
            if r["timed_out"]:
                break
        return res

    def shell(self, cmd: str, **kw) -> dict:
        """Alias de `run` para cuando no sabes qué prompt esperar."""
        return self.run(cmd, **kw)


def console_for(client: Client, pid: str, node: dict) -> Console:
    """Abre la consola telnet del nodo o explica por qué no se puede."""
    ctype = (node.get("console_type") or "").lower()
    port = node.get("console")
    if ctype != "telnet":
        raise ConsoleError(
            f"{node['name']} usa consola '{ctype or 'none'}' (no telnet). "
            f"Para nodos gráficos usa el monitor QEMU: gns3_monitor / `gns3lab key|shot`."
        )
    if not port:
        full = client.get(f"/v2/projects/{pid}/nodes/{node['node_id']}")
        if full[0] == 200 and isinstance(full[1], dict):
            port = full[1].get("console")
    if not port:
        raise ConsoleError(f"{node['name']} no expone puerto de consola")
    host = node.get("console_host") or "127.0.0.1"
    if host in ("0.0.0.0", ""):
        host = "127.0.0.1"
    return Console(host, int(port))


# ─────────────────────────── monitor QEMU (HMP) ───────────────────────────
KEYMAP = {
    " ": "spc", "-": "minus", "=": "equal", ".": "dot", ",": "comma",
    "/": "slash", ";": "semicolon", "'": "apostrophe", "`": "grave_accent",
    "\\": "backslash", "[": "bracket_left", "]": "bracket_right",
    "!": "shift-1", "@": "shift-2", "#": "shift-3", "$": "shift-4", "%": "shift-5",
    "^": "shift-6", "&": "shift-7", "*": "shift-8", "(": "shift-9", ")": "shift-0",
    "_": "shift-minus", "+": "shift-equal", "{": "shift-bracket_left",
    "}": "shift-bracket_right", "|": "shift-backslash", ":": "shift-semicolon",
    '"': "shift-apostrophe", "<": "shift-comma", ">": "shift-dot",
    "?": "shift-slash", "~": "shift-grave_accent",
}
NAMED = {"\n": "ret", "\r": "ret", "\t": "tab", " ": "spc"}


def key_for(ch: str) -> Optional[str]:
    """Traduce un carácter al nombre de tecla de HMP (`sendkey`)."""
    if ch in NAMED:
        return NAMED[ch]
    if ch in KEYMAP:
        return KEYMAP[ch]
    if "a" <= ch <= "z" or "0" <= ch <= "9":
        return ch
    if "A" <= ch <= "Z":
        return "shift-" + ch.lower()
    return None


def find_monitor_port(node_id: Optional[str] = None, disk: Optional[str] = None) -> Optional[int]:
    """Puerto HMP del proceso QEMU de un nodo, leyendo /proc.

    GNS3 pasa el `node_id` como `-uuid` a QEMU, así que es la identificación exacta;
    si no, se busca por el nombre del disco en el cmdline.
    """
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            raw = (proc / "cmdline").read_bytes()
        except (OSError, PermissionError):
            continue
        if b"qemu-system" not in raw:
            continue
        args = [a.decode(errors="replace") for a in raw.split(b"\0") if a]
        joined = " ".join(args)
        if node_id and node_id not in joined:
            continue
        if disk and disk not in joined:
            continue
        for i, a in enumerate(args):
            if a.startswith("-monitor") and "tcp:" in a:
                m = re.search(r"tcp:([\d.]+):(\d+)", a)
                if m:
                    return int(m.group(2))
            if a == "-monitor" and i + 1 < len(args):
                m = re.search(r"tcp:([\d.]+):(\d+)", args[i + 1])
                if m:
                    return int(m.group(2))
    return None


class QemuMonitor:
    """Canal HMP de un nodo QEMU: teclas y captura real del framebuffer."""

    def __init__(self, port: int, timeout: float = 6.0):
        self.port = port
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.sock.settimeout(0.3)
        self.banner = self._read(0.6)

    @classmethod
    def for_node(cls, node_id: Optional[str] = None, disk: Optional[str] = None) -> "QemuMonitor":
        port = find_monitor_port(node_id, disk)
        if not port:
            raise RuntimeError(
                "no encuentro el monitor del nodo QEMU. Comprueba que el nodo está arrancado "
                "y que /proc es legible."
            )
        return cls(port)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def _read(self, seconds: float = 0.5) -> str:
        buf = b""
        end = time.time() + seconds
        while time.time() < end:
            try:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
            except socket.timeout:
                continue
            except OSError:
                break
        return buf.decode(errors="replace")

    def run(self, cmd: str, timeout: float = 6.0) -> dict:
        """Envía un comando HMP y devuelve la respuesta sin el eco."""
        self.sock.sendall((cmd + "\n").encode())
        raw = self._read(0.35)
        deadline = time.time() + timeout
        while "(qemu)" not in raw and time.time() < deadline:
            chunk = self._read(0.3)
            if not chunk:
                break
            raw += chunk
        text = clean(raw)
        # HMP hace eco carácter a carácter con borrados: la 1ª línea es ruido
        lines = [ln for ln in text.split("\n")]
        body = "\n".join(lines[1:]).replace("(qemu) ", "").strip()
        err = None
        m = re.search(r"(?:Error|error):\s*(.+)", body)
        if m:
            err = m.group(1).strip()
        return {"cmd": cmd, "output": body, "error": err, "raw_len": len(raw)}

    # -- teclas ---------------------------------------------------------------
    def sendkey(self, *keys: str, delay: float = 0.06) -> dict:
        """Manda teclas por nombre HMP (`ret`, `shift-2`, `a`)."""
        out = []
        for k in keys:
            self.sock.sendall(f"sendkey {k}\n".encode())
            time.sleep(delay)
            out.append(self._read(0.08))
        return {"sent": list(keys)}

    def type_text(self, text: str, delay: float = 0.08, wake: bool = True) -> dict:
        """Escribe un texto traduciendo cada carácter a `sendkey`.

        Con `wake` manda antes un `sendkey shift`: la consola del invitado duerme tras
        un rato sin entrada y se come la primera tecla, con lo que el primer carácter
        se pierde en silencio (el menú se queda como estaba).
        """
        unknown = []
        sent = 0
        if wake:
            self.sock.sendall(b"sendkey shift\n")
            time.sleep(0.3)
            self._read(0.1)
        for ch in text:
            k = key_for(ch)
            if not k:
                unknown.append(ch)
                continue
            self.sock.sendall(f"sendkey {k}\n".encode())
            sent += 1
            time.sleep(delay)
        self._read(0.2)
        return {"typed": text, "keys_sent": sent, "unknown": unknown}

    def screendump(self, dest: Optional[str] = None, scale: int = 0) -> dict:
        """Captura el framebuffer real y la deja en PNG (PPM -> PNG con Pillow)."""
        stamp = time.strftime("%Y%m%d-%H%M%S")
        base = Path(dest).expanduser() if dest else Path.home() / "GNS3/captures" / f"screen-{stamp}.png"
        base.parent.mkdir(parents=True, exist_ok=True)
        ppm = base.with_suffix(".ppm")
        if ppm.exists():
            ppm.unlink()
        res = self.run(f"screendump {ppm}")
        for _ in range(20):
            if ppm.exists() and ppm.stat().st_size > 1000:
                break
            time.sleep(0.1)
        if not ppm.exists():
            return {"error": "screendump no generó fichero", "detail": res}
        png = base
        try:
            from PIL import Image
            img = Image.open(ppm)
            if scale and scale > 1:
                img = img.resize((img.width * scale, img.height * scale))
            img.convert("L").save(png)
            size = img.size
            ppm.unlink(missing_ok=True)
        except Exception as e:                     # sin Pillow: ImageMagick o el PPM
            conv = shutil.which("magick") or shutil.which("convert")
            if conv:
                r = subprocess.run([conv, str(ppm), str(base)], capture_output=True, text=True)
                if r.returncode == 0:
                    ppm.unlink(missing_ok=True)
                    return {"path": str(base), "size": None,
                            "bytes": base.stat().st_size, "converted_by": "magick"}
            png = ppm
            size = None
            res["pillow_error"] = str(e)
        return {"path": str(png), "size": size, "bytes": png.stat().st_size}


def ocr(path: str, psm: int = 6) -> str:
    """Texto del PNG con tesseract. `psm 6` = bloque uniforme (menús)."""
    if not shutil.which("tesseract"):
        return ""
    try:
        r = subprocess.run(["tesseract", path, "stdout", "--psm", str(psm)],
                           capture_output=True, text=True, timeout=60)
        # la fuente VGA confunde `w` con `u`; se corrige lo que rompe comandos
        return r.stdout.strip().replace("Shou", "Show").replace("shou", "show")
    except (subprocess.SubprocessError, OSError):
        return ""


def screen_text(monitor: "QemuMonitor", psm: int = 4, scale: int = 2) -> dict:
    """Captura + OCR en un paso: lo que hay en pantalla, como texto.

    720x400 (fuente 9x16) lee mal a escala 1; x2 con psm 4 es el punto dulce medido
    sobre el menú de pfSense: recupera `--show-tls` donde x1 devolvía `--shou-t1s`.
    """
    shot = monitor.screendump(scale=scale)
    if shot.get("error"):
        return shot
    shot["ocr"] = ocr(shot["path"], psm=psm)
    return shot
