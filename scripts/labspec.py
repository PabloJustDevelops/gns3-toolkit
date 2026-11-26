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
CLAVES_TOP = {"version", "project", "nodes", "links", "expect", "warn"}
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

    warn = data.get("warn", [])
    if not isinstance(warn, list) or any(
            not isinstance(mensaje, str) or not mensaje.strip() for mensaje in warn):
        errores.append("warn: debe ser una lista de mensajes no vacíos")

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
    salida = {"version": VERSION, "project": data["project"],
              "nodes": nodos, "links": enlaces, "expect": expect}
    if "warn" in data:
        salida["warn"] = list(data["warn"])
    return salida


def export(topology: dict, project: str | None = None) -> dict:
    """Convierte una topología leída en un spec v1 sin inventar configuración."""
    if not isinstance(topology, dict):
        raise SpecError("topología: la raíz debe ser un mapa JSON")

    nombre_proyecto = project if project is not None else topology.get("project")
    if isinstance(nombre_proyecto, dict):
        nombre_proyecto = nombre_proyecto.get("name")
    nodos_raw = topology.get("nodes", [])
    if not isinstance(nodos_raw, list):
        raise SpecError("topología.nodes: debe ser una lista")

    nodos = []
    for nodo in nodos_raw:
        if not isinstance(nodo, dict):
            raise SpecError("topología.nodes: cada nodo debe ser un mapa")
        limpio = {"name": nodo.get("name"),
                  "template": nodo.get("node_type") or nodo.get("template")}
        properties = nodo.get("properties")
        if isinstance(properties, dict) and properties.get("adapter_type") is not None:
            limpio["adapter_type"] = properties["adapter_type"]
        nodos.append(limpio)

    candidato = {"version": VERSION, "project": nombre_proyecto,
                 "nodes": nodos, "links": [], "expect": {}}
    errores = validar(candidato)
    if errores:
        raise SpecError("topología no exportable: " + "; ".join(errores))

    nombres = {nodo["name"] for nodo in nodos}
    enlaces_raw = topology.get("links", [])
    if not isinstance(enlaces_raw, list):
        raise SpecError("topología.links: debe ser una lista")
    enlaces = []
    warn = []
    for i, enlace in enumerate(enlaces_raw):
        base = f"links[{i}]"
        ends = enlace.get("ends") if isinstance(enlace, dict) else None
        if not isinstance(ends, (list, tuple)) or len(ends) != 2:
            warn.append(f"{base}: omitido (no tiene dos extremos)")
            continue
        extremos = []
        for extremo in ends:
            if not isinstance(extremo, dict):
                extremos = []
                break
            nombre = extremo.get("node")
            adapter = extremo.get("adapter", 0)
            if isinstance(adapter, str) and adapter.isdigit():
                adapter = int(adapter)
            if (not isinstance(nombre, str) or nombre not in nombres
                    or not _es_entero(adapter) or adapter < 0):
                extremos = []
                break
            extremos.append((nombre, adapter))
        if len(extremos) != 2:
            warn.append(f"{base}: omitido (extremo o adapter inválido)")
            continue
        if extremos[0][0] == extremos[1][0]:
            warn.append(f"{base}: omitido (un nodo no puede enlazarse consigo mismo)")
            continue
        enlaces.append({"a": extremos[0][0], "b": extremos[1][0],
                        "pa": extremos[0][1], "pb": extremos[1][1]})

    candidato["links"] = enlaces
    salida = normalizar(candidato)
    if warn:
        salida["warn"] = warn
    return salida


def _clave_enlace(enlace: dict) -> tuple:
    """Identidad independiente del orden de los dos extremos."""
    a = (enlace["a"], enlace.get("pa", 0))
    b = (enlace["b"], enlace.get("pb", 0))
    if b < a:
        a, b = b, a
    return (a[0], a[1], b[0], b[1])


def diff(deseado: dict, actual: dict) -> dict:
    """Compara por nombre y por extremos normalizados; nunca propone borrados."""
    nodos_deseados = {nodo["name"]: nodo for nodo in deseado.get("nodes", [])}
    nodos_actuales = {nodo["name"] for nodo in actual.get("nodes", [])}
    crear_nodos = [
        {clave: nodos_deseados[nombre][clave]
         for clave in ("name", "template", "adapter_type") if clave in nodos_deseados[nombre]}
        for nombre in sorted(nodos_deseados.keys() - nodos_actuales)
    ]

    enlaces_deseados = {_clave_enlace(e): e for e in deseado.get("links", [])}
    enlaces_actuales = {_clave_enlace(e): e for e in actual.get("links", [])}
    crear_enlaces = [enlaces_deseados[clave]
                     for clave in sorted(enlaces_deseados.keys() - enlaces_actuales.keys())]
    sobrantes_enlaces = [enlaces_actuales[clave]
                         for clave in sorted(enlaces_actuales.keys() - enlaces_deseados.keys())]
    sobrantes_nodos = sorted(nodos_actuales - nodos_deseados.keys())
    sin_cambios = not (crear_nodos or crear_enlaces or sobrantes_nodos or sobrantes_enlaces)
    return {"crear_nodos": crear_nodos, "crear_enlaces": crear_enlaces,
            "sobrantes_nodos": sobrantes_nodos, "sobrantes_enlaces": sobrantes_enlaces,
            "sin_cambios": sin_cambios}


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


def plan(deseado: dict, actual: dict, server: str | None = None) -> list[list[str]]:
    """Órdenes para crear sólo lo que falta; `server` lo añade el ejecutor."""
    cambios = diff(deseado, actual)
    if not cambios["crear_nodos"] and not cambios["crear_enlaces"]:
        return []
    proyecto = deseado["project"]
    cmds = [] if actual.get("project") else [["new", proyecto]]
    for nodo in cambios["crear_nodos"]:
        cmds.append(["node", "add", "--template", nodo["template"],
                     "--name", nodo["name"], "-p", proyecto])
        if nodo.get("adapter_type"):
            cmds.append(["node", "props", nodo["name"], "--set",
                         f"adapter_type={nodo['adapter_type']}", "-p", proyecto])
    for enlace in cambios["crear_enlaces"]:
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


def aplicar_deseado(deseado: dict, actual: dict, server: str | None, yes: bool) -> int:
    cmds = plan(deseado, actual, server)
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
    print(f"{deseado['project']}: aplicado ({len(cmds)} órdenes)")
    return 0


def aplicar(spec: dict, server: str | None, yes: bool) -> int:
    """Compatibilidad: crea el proyecto como en la v1 original."""
    return aplicar_deseado(spec, {}, server, yes)


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


def _leer_topologia(ruta: str | None = None, stdin: bool = False) -> dict:
    origen = "<stdin>" if stdin else str(ruta)
    try:
        texto = sys.stdin.read() if stdin else Path(ruta).read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecError(f"{origen}: no se puede leer ({exc})") from exc
    try:
        data = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise SpecError(f"{origen}: JSON inválido: {exc}") from exc
    if not isinstance(data, dict):
        raise SpecError(f"{origen}: la raíz debe ser un mapa JSON")
    return data


def _actual_desde_topologia(topology: dict) -> dict:
    """Exportación tolerante con un proyecto real vacío para poder hacer diff."""
    if topology.get("nodes") == []:
        return {"project": topology.get("project"), "nodes": [], "links": []}
    return export(topology)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="laboratorio declarativo sobre gns3lab (sin borrar nada)")
    ap.add_argument("--server", "-s", help="servidor gns3lab (se pasa a la CLI)")
    ap.add_argument("--json", action="store_true", help="salida JSON para diff")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nombre, ayuda in (("validate", "valida el YAML y reporta errores"),
                          ("plan", "imprime las órdenes gns3lab sin ejecutarlas"),
                          ("verify", "comprueba el laboratorio con lecturas")):
        p = sub.add_parser(nombre, help=ayuda)
        p.add_argument("spec", help="fichero YAML del laboratorio")
    p = sub.add_parser("apply", help="crea el laboratorio con la CLI existente")
    p.add_argument("--yes", action="store_true", help="obligatorio: confirma la escritura")
    p.add_argument("spec", help="fichero YAML del laboratorio")

    p = sub.add_parser("export", help="exporta una topología JSON a spec v1")
    origen = p.add_mutually_exclusive_group(required=True)
    origen.add_argument("--topology", help="fichero JSON con la topología ya obtenida")
    origen.add_argument("--stdin", action="store_true", help="lee la topología JSON de stdin")
    p.add_argument("--project", help="nombre de proyecto que sobrescribe al de la topología")

    p = sub.add_parser("diff", help="compara el spec deseado con una topología JSON")
    p.add_argument("--spec", required=True, help="fichero YAML del laboratorio deseado")
    p.add_argument("--topology", required=True, help="fichero JSON con la topología actual")
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="salida JSON (también es el formato por defecto)")
    args = ap.parse_args(argv)

    if args.cmd == "export":
        try:
            salida = export(_leer_topologia(args.topology, args.stdin), args.project)
        except SpecError as exc:
            print(f"ERROR: {exc}")
            return 1
        print(json.dumps(salida, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "diff":
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
        try:
            salida = diff(normalizar(data), _actual_desde_topologia(_leer_topologia(args.topology)))
        except SpecError as exc:
            print(f"ERROR: {exc}")
            return 1
        print(json.dumps(salida, ensure_ascii=False, indent=2))
        return 0

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
