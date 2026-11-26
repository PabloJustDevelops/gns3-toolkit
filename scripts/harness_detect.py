#!/usr/bin/env python3
"""Detecta los cinco harnesses soportados y su versión. Solo lectura.

No instala nada, no usa la red y no lanza prompts: `shutil.which` para
localizar el binario y `--version` con timeout corto para leer la versión.
Con `--json` devuelve un objeto con `harnesses`, `missing` y `exit_code`.
El proceso sale con 0 si están los cinco y con 1 si falta alguno; una versión
ilegible o un timeout se anotan en `notes`, no cambian el código de salida.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys

TIMEOUT = 5.0
VERSION_RE = re.compile(r"\d+\.\d+\.\d+")

# Comando canónico para este repo, si acepta trabajo headless y límites reales.
HARNESSES: dict[str, dict] = {
    "cmdc": {
        "command": 'cmdc -p "<brief>" --yolo',
        "headless": True,
        "notes": "headless con -p/--print; -w crea worktree; MCP con mcp add-json",
        "version_args": ["--version"],
    },
    "opencode": {
        "command": 'opencode run --auto --file brief.md "ejecuta el brief"',
        "headless": True,
        "notes": "headless con run; --archived para CI; MCP con mcp add",
        "version_args": ["--version"],
    },
    "hermes": {
        "command": 'hermes chat -q "<brief>" --oneshot --yolo',
        "headless": True,
        "notes": "headless con chat -q --oneshot; -z es atajo; MCP con mcp add",
        "version_args": ["--version"],
    },
    "freebuff": {
        "command": "freebuff --cwd .",
        "headless": False,
        "notes": "sin modo headless; TUI; MCP no verificado (solo --trust-agents)",
        "version_args": ["--version"],
    },
    "codex": {
        "command": 'codex exec "<brief>"',
        "headless": True,
        "notes": "headless con exec; resume reanuda; MCP con mcp add",
        "version_args": ["--version"],
    },
}


def parse_version(salida: str) -> str | None:
    """Primera versión `X.Y.Z` de la primera línea con contenido."""
    for linea in (salida or "").splitlines():
        if linea.strip():
            hallado = VERSION_RE.search(linea)
            return hallado.group(0) if hallado else None
    return None


def detect(nombre: str, *, which=None, run=None) -> dict:
    """Ficha de un harness. Nunca lanza: los fallos van a `notes`."""
    which = which or shutil.which
    run = run or subprocess.run
    config = HARNESSES[nombre]
    ruta = which(nombre)
    entrada = {
        "harness": nombre,
        "path": ruta,
        "version": None,
        "command": config["command"],
        "headless": config["headless"],
        "notes": config["notes"],
    }
    if ruta is None:
        entrada["notes"] += " · no instalado"
        return entrada
    try:
        proc = run(
            [ruta, *config["version_args"]],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        entrada["notes"] += f" · --version agotó el tiempo ({TIMEOUT:g} s)"
        return entrada
    except OSError as exc:
        entrada["notes"] += f" · --version no se pudo ejecutar ({exc})"
        return entrada

    version = parse_version(f"{proc.stdout or ''}\n{proc.stderr or ''}")
    if version is None:
        entrada["notes"] += " · versión no parseable"
    else:
        entrada["version"] = version
    if proc.returncode != 0:
        entrada["notes"] += f" · --version salió con {proc.returncode}"
    return entrada


def detect_all(*, which=None, run=None) -> list[dict]:
    return [detect(nombre, which=which, run=run) for nombre in HARNESSES]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="detecta harnesses y su versión, sin ejecutar prompts")
    ap.add_argument("--json", action="store_true", help="salida JSON con exit_code incluido")
    args = ap.parse_args(argv)

    entradas = detect_all()
    faltan = [e["harness"] for e in entradas if e["path"] is None]
    codigo = 1 if faltan else 0

    if args.json:
        print(json.dumps(
            {"harnesses": entradas, "missing": faltan, "exit_code": codigo},
            ensure_ascii=False,
            indent=2,
        ))
        return codigo

    for entrada in entradas:
        ruta = entrada["path"] or "-"
        version = entrada["version"] or "?"
        modo = "headless" if entrada["headless"] else "interactivo"
        print(f"{entrada['harness']:<9} {version:<10} {modo:<12} {ruta}")
        print(f"          {entrada['notes']}")
    print(f"faltan: {', '.join(faltan) if faltan else 'ninguno'}")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
