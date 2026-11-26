#!/usr/bin/env python3
"""Laboratorio declarativo: valida, planifica, aplica y verifica un YAML pequeño.

Sólo orquesta la CLI existente (`new`, `node add`, `node props`, `link add`,
`up` para escribir; `status`, `link list`, `exec`, `pf detect` para leer).
No habla con la API ni borra proyectos o nodos.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "cli" / "gns3lab"
VERSION = 1
CLAVES_TOP = {"version", "project", "nodes", "links", "expect"}
CLAVES_NODO = {"name", "template", "adapter_type", "ip"}
CLAVES_ENLACE = {"a", "b", "pa", "pb"}
NOMBRE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class SpecError(Exception):
    """El fichero no se puede leer o no es un mapa YAML."""


def leer(ruta: str) -> dict:
    try:
        texto = Path(ruta).read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecError(f"{ruta}: no se puede leer ({exc})") from exc
    try:
        data = yaml.safe_load(texto)
    except yaml.YAMLError as exc:
        raise SpecError(f"{ruta}: YAML inválido: {exc}") from exc
    if not isinstance(data, dict):
        raise SpecError(f"{ruta}: la raíz debe ser un mapa YAML")
    return data


def _es_entero(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def validar(data: dict) -> list[str]:
    """Devuelve todos los errores con la ruta del campo; vacío si es válido."""
    errores: list[str] = []

    for clave in data:
        if clave not in CLAVES_TOP:
            errores.append(f"{clave}: clave desconocida")

    version = data.get("version")
    if not _es_entero(version) or version != VERSION:
        errores.append(f"version: debe ser {VERSION}")

    project = data.get("project")
    if not isinstance(project, str) or not project.strip():
        errores.append("project: obligatorio y no vacío")
    elif not NOMBRE_RE.match(project):
        errores.append("project: sólo letras, dígitos, punto, guion y guion bajo")

    nombres: list[str] = []
    nodos = data.get("nodes")
    if not isinstance(nodos, list) or not nodos:
        errores.append("nodes: lista no vacía obligatoria")
        nodos = []
    for i, nodo in enumerate(nodos):
        base = f"nodes[{i}]"
        if not isinstance(nodo, dict):
            errores.append(f"{base}: debe ser un mapa")
            continue
        for clave in nodo:
            if clave not in CLAVES_NODO:
                errores.append(f"{base}.{clave}: clave desconocida")
        nombre = nodo.get("name")
        if not isinstance(nombre, str) or not nombre.strip():
            errores.append(f"{base}.name: obligatorio y no vacío")
        elif not NOMBRE_RE.match(nombre):
            errores.append(f"{base}.name: sólo letras, dígitos, punto, guion y guion bajo")
        elif nombre in nombres:
            errores.append(f"{base}.name: nombre duplicado {nombre!r}")
        else:
            nombres.append(nombre)
        plantilla = nodo.get("template")
        if not isinstance(plantilla, str) or not plantilla.strip():
            errores.append(f"{base}.template: obligatorio y no vacío")
        adapter = nodo.get("adapter_type")
        if adapter is not None and (not isinstance(adapter, str) or not adapter.strip()):
            errores.append(f"{base}.adapter_type: debe ser texto no vacío")
        ip = nodo.get("ip")
        if ip is not None:
            if not isinstance(ip, str) or not ip.strip():
                errores.append(f"{base}.ip: debe ser texto (IP o IP/máscara)")
            else:
                try:
                    ipaddress.ip_interface(ip)
                except ValueError:
                    errores.append(f"{base}.ip: IP inválida {ip!r}")

    enlaces = data.get("links", [])
    if not isinstance(enlaces, list):
        errores.append("links: debe ser una lista")
        enlaces = []
    for i, enlace in enumerate(enlaces):
        base = f"links[{i}]"
        if not isinstance(enlace, dict):
            errores.append(f"{base}: debe ser un mapa")
            continue
        for clave in enlace:
            if clave not in CLAVES_ENLACE:
                errores.append(f"{base}.{clave}: clave desconocida")
        extremos = []
        for lado in ("a", "b"):
            valor = enlace.get(lado)
            if not isinstance(valor, str) or not valor.strip():
                errores.append(f"{base}.{lado}: obligatorio y no vacío")
            elif valor not in nombres:
                errores.append(f"{base}.{lado}: nodo desconocido {valor!r}")
            else:
                extremos.append(valor)
        if len(extremos) == 2 and extremos[0] == extremos[1]:
            errores.append(f"{base}: un nodo no puede enlazarse consigo mismo")
        for puerto in ("pa", "pb"):
            valor = enlace.get(puerto, 0)
            if not _es_entero(valor) or valor < 0:
                errores.append(f"{base}.{puerto}: debe ser entero >= 0")

    expect = data.get("expect", {})
    if not isinstance(expect, dict):
        errores.append("expect: debe ser un mapa nodo -> lista de comandos")
        expect = {}
    for nombre, comandos in expect.items():
        base = f"expect.{nombre}"
        if nombre not in nombres:
            errores.append(f"{base}: nodo desconocido {nombre!r}")
        if not isinstance(comandos, list) or not comandos:
            errores.append(f"{base}: lista de comandos no vacía obligatoria")
            continue
        for i, comando in enumerate(comandos):
            if not isinstance(comando, str) or not comando.strip():
                errores.append(f"{base}[{i}]: comando no vacío obligatorio")

    return errores


def normalizar(data: dict) -> dict:
    """Forma canónica que usan plan, apply y verify (sólo tras validar)."""
    nodos = []
    for nodo in data["nodes"]:
        limpio = {k: nodo[k] for k in ("name", "template")}
        if nodo.get("adapter_type"):
            limpio["adapter_type"] = nodo["adapter_type"]
        if nodo.get("ip"):
            limpio["ip"] = nodo["ip"]
        nodos.append(limpio)
    enlaces = [{"a": e["a"], "b": e["b"], "pa": e.get("pa", 0), "pb": e.get("pb", 0)}
               for e in data.get("links", [])]
    expect = {k: list(v) for k, v in (data.get("expect") or {}).items()}
    return {"version": VERSION, "project": data["project"],
            "nodes": nodos, "links": enlaces, "expect": expect}


def ordenes(spec: dict) -> list[list[str]]:
    """Órdenes gns3lab, sólo con subcomandos existentes y sin borrar nada."""
    proyecto = spec["project"]
    cmds = [["new", proyecto]]
    for nodo in spec["nodes"]:
        cmds.append(["node", "add", "--template", nodo["template"],
                     "--name", nodo["name"], "-p", proyecto])
        if nodo.get("adapter_type"):
            cmds.append(["node", "props", nodo["name"], "--set",
                         f"adapter_type={nodo['adapter_type']}", "-p", proyecto])
    for enlace in spec["links"]:
        cmds.append(["link", "add", enlace["a"], enlace["b"],
                     "--pa", str(enlace["pa"]), "--pb", str(enlace["pb"]),
                     "-p", proyecto])
    cmds.append(["up", proyecto])
    return cmds


def _con_servidor(argv: list[str], server: str | None) -> list[str]:
    return (["--server", server] if server else []) + list(argv)


def _mostrar(argv: list[str], server: str | None) -> str:
    return "gns3lab " + shlex.join(_con_servidor(argv, server))


def _orden_real(argv: list[str], server: str | None) -> list[str]:
    return [sys.executable, str(CLI)] + _con_servidor(argv, server)


def ejecutar(argv: list[str], server: str | None = None) -> int:
    """Ejecuta la CLI dejando su salida en pantalla."""
    return subprocess.run(_orden_real(argv, server), text=True, check=False).returncode


def capturar(argv: list[str], server: str | None = None) -> tuple[int, str]:
    """Ejecuta la CLI de solo lectura y devuelve (exit, stdout+stderr)."""
    proc = subprocess.run(_orden_real(argv, server), text=True,
                          capture_output=True, check=False)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def aplicar(spec: dict, server: str | None, yes: bool) -> int:
    cmds = ordenes(spec)
    if not yes:
        for argv in cmds:
            print(_mostrar(argv, server))
        print("apply escribe en GNS3: repite con --yes (no se ha ejecutado nada)",
              file=sys.stderr)
        return 2
    for argv in cmds:
        print(f"$ {_mostrar(argv, server)}")
        rc = ejecutar(argv, server)
        if rc != 0:
            print(f"falló con exit {rc}; no sigo. No se borra nada.", file=sys.stderr)
            return rc
    print(f"{spec['project']}: aplicado ({len(cmds)} órdenes)")
    return 0


def _nodos_de_status(salida: str, proyecto: str) -> dict[str, tuple[str, str]] | None:
    """Nodos del proyecto abierto en `gns3lab status`; None si no aparece."""
    cabecera = False
    nodos: dict[str, tuple[str, str]] = {}
    for linea in salida.splitlines():
        if linea.startswith(" *"):
            partes = linea.split()
            cabecera = (len(partes) > 1 and partes[1] == proyecto
                        and "abierto" in partes)
            continue
        if not cabecera or not linea.startswith("      "):
            continue
        partes = linea.split()
        if len(partes) >= 3:
            nodos[partes[0]] = (partes[1], partes[2])
    return nodos if cabecera else None


def _extremos(salida: str) -> set[tuple]:
    """Pares normalizados ((nodo, adapter, puerto), ...) de `link list`."""
    pares = set()
    for linea in salida.splitlines():
        if " <-> " not in linea:
            continue
        extremos = []
        for lado in linea.split(" <-> "):
            # El primer lado arrastra el id del enlace; el nombre no tiene espacios.
            trozo = lado.strip().split()[-1]
            nombre, _, puerto = trozo.partition(":")
            adapter, _, numero = puerto.partition("/")
            if not nombre or not numero:
                break
            extremos.append((nombre, adapter, numero))
        if len(extremos) == 2:
            pares.add(tuple(sorted(extremos)))
    return pares


def verificar(spec: dict, server: str | None) -> int:
    proyecto = spec["project"]
    fallos = 0

    rc, salida = capturar(["status", proyecto], server)
    nodos = _nodos_de_status(salida, proyecto) if rc == 0 else None
    if nodos is None:
        print(f"proyecto {proyecto}: no aparece abierto en `status` (exit {rc})")
        print(salida.strip())
        print("RESULTADO: FALLO")
        return 1

    for nodo in spec["nodes"]:
        nombre = nodo["name"]
        if nombre not in nodos:
            print(f"nodo {nombre}: FALLO (no está en el proyecto)")
            fallos += 1
            continue
        tipo, estado = nodos[nombre]
        if estado != "started":
            print(f"nodo {nombre} ({tipo}, {estado}): FALLO (no arrancado)")
            fallos += 1
            continue
        print(f"nodo {nombre} ({tipo}, {estado}): OK")

        if nodo.get("adapter_type"):
            rc, salida = capturar(["pf", "detect", "--json", "--node", nombre,
                                   "-p", proyecto], server)
            leido = ""
            try:
                datos = json.loads(salida)
                leido = str((datos.get("data") or {}).get("adapter_type") or "")
            except (ValueError, AttributeError):
                pass
            if rc != 0:
                print(f"  pf detect: FALLO (exit {rc})")
                fallos += 1
            elif leido != nodo["adapter_type"]:
                print(f"  pf detect: FALLO (adapter_type={leido or '?'}, "
                      f"pedido {nodo['adapter_type']})")
                fallos += 1
            else:
                print(f"  pf detect: OK (adapter_type={leido})")

        if nodo.get("ip"):
            if tipo == "vpcs":
                rc, salida = capturar(["exec", nombre, "show ip", "-p", proyecto], server)
                esperada = str(ipaddress.ip_interface(nodo["ip"]).ip)
                if rc != 0:
                    print(f"  ip {nodo['ip']}: FALLO (exit {rc})")
                    fallos += 1
                elif esperada not in salida:
                    print(f"  ip {nodo['ip']}: FALLO (la consola no muestra {esperada})")
                    fallos += 1
                else:
                    print(f"  ip {nodo['ip']}: OK")
            else:
                print(f"  ip {nodo['ip']}: omitido (sólo se comprueba en VPCS)")

        for comando in spec["expect"].get(nombre, []):
            rc, salida = capturar(["exec", nombre, comando, "-p", proyecto], server)
            if rc != 0 or "[timeout" in salida:
                print(f"  expect `{comando}`: FALLO (exit {rc})")
                fallos += 1
            else:
                print(f"  expect `{comando}`: OK")

    rc, salida = capturar(["link", "list", "-p", proyecto], server)
    existentes = _extremos(salida) if rc == 0 else set()
    if rc != 0:
        print(f"enlaces: FALLO (no se pudo listar, exit {rc})")
        fallos += 1
    for enlace in spec["links"]:
        pedido = tuple(sorted(((enlace["a"], str(enlace["pa"]), "0"),
                               (enlace["b"], str(enlace["pb"]), "0"))))
        # El puerto puede ser distinto del 0 por defecto del switch: se compara
        # por nodo y adapter, que es lo que declara el YAML.
        pedido_sin_puerto = tuple(sorted((n, a) for n, a, _ in pedido))
        cortos = {tuple(sorted((n, a) for n, a, _ in par)) for par in existentes}
        if pedido_sin_puerto in cortos:
            print(f"enlace {enlace['a']}:{enlace['pa']} <-> "
                  f"{enlace['b']}:{enlace['pb']}: OK")
        else:
            print(f"enlace {enlace['a']}:{enlace['pa']} <-> "
                  f"{enlace['b']}:{enlace['pb']}: FALLO (no existe)")
            fallos += 1

    print(f"RESULTADO: {'OK' if not fallos else 'FALLO'} "
          f"({len(spec['nodes'])} nodos, {len(spec['links'])} enlaces)")
    return 0 if not fallos else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="laboratorio declarativo sobre gns3lab (sin borrar nada)")
    ap.add_argument("--server", "-s", help="servidor gns3lab (se pasa a la CLI)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nombre, ayuda in (("validate", "valida el YAML y reporta errores"),
                          ("plan", "imprime las órdenes gns3lab sin ejecutarlas"),
                          ("verify", "comprueba el laboratorio con lecturas")):
        p = sub.add_parser(nombre, help=ayuda)
        p.add_argument("spec", help="fichero YAML del laboratorio")
    p = sub.add_parser("apply", help="crea el laboratorio con la CLI existente")
    p.add_argument("--yes", action="store_true", help="obligatorio: confirma la escritura")
    p.add_argument("spec", help="fichero YAML del laboratorio")
    args = ap.parse_args(argv)

    try:
        data = leer(args.spec)
    except SpecError as exc:
        print(f"ERROR: {exc}")
        return 1

    errores = validar(data)
    if errores:
        for error in errores:
            print(f"{args.spec}: {error}")
        print(f"INVÁLIDO: {len(errores)} error(es)")
        return 1
    spec = normalizar(data)

    if args.cmd == "validate":
        print(f"OK: {spec['project']} ({len(spec['nodes'])} nodos, "
              f"{len(spec['links'])} enlaces)")
        return 0
    if args.cmd == "plan":
        for argv_cmd in ordenes(spec):
            print(_mostrar(argv_cmd, args.server))
        return 0
    if not CLI.is_file():
        print(f"falta la CLI {CLI}: ejecuta ./scripts/install.sh", file=sys.stderr)
        return 2
    if args.cmd == "apply":
        return aplicar(spec, args.server, args.yes)
    return verificar(spec, args.server)


if __name__ == "__main__":
    sys.exit(main())
