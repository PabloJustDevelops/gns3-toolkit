#!/usr/bin/env python3
"""Comprueba enlaces relativos rotos en todos los .md del repo. Solo lectura.

Recorre la raíz indicada (por defecto, la del repo), salta `.git`, `.venv` y
`__pycache__`, e ignora enlaces absolutos (`http:`, `mailto:`, `//...`) y las
anclas puras. Salida: un hallazgo por línea con `fichero:línea`. Exit code 0
sin enlaces rotos, 1 si encuentra alguno.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

SALTAR_DIRS = {".git", ".venv", "__pycache__"}
ENLACE_RE = re.compile(r"\[[^\]]*\]\(\s*(<[^>]*>|[^)\s]+)")
REFERENCIA_RE = re.compile(r"^\s{0,3}\[(?!\^)[^\]]+\]:\s*(\S+)")
ESQUEMA_RE = re.compile(r"^[a-zA-Z][\w+.-]*:|^//")
CODIGO_INLINE_RE = re.compile(r"`[^`]*`")


def rel(ruta: Path, root: Path) -> str:
    try:
        return str(ruta.relative_to(root))
    except ValueError:
        return str(ruta)


def destino_roto(ruta: Path, destino: str) -> bool:
    destino = destino.strip()
    if destino.startswith("<") and destino.endswith(">"):
        destino = destino[1:-1]
    destino = unquote(destino.split("#", 1)[0].split("?", 1)[0])
    if not destino or ESQUEMA_RE.match(destino):
        return False
    return not (ruta.parent / destino).resolve().exists()


def enlaces_rotos(root: Path) -> list[str]:
    hallazgos = []
    for ruta in sorted(root.rglob("*.md")):
        if SALTAR_DIRS.intersection(ruta.relative_to(root).parts):
            continue
        try:
            lineas = ruta.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            hallazgos.append(f"{rel(ruta, root)}: no se puede leer ({exc})")
            continue
        en_bloque = False
        for numero, linea in enumerate(lineas, 1):
            if linea.lstrip().startswith(("```", "~~~")):
                en_bloque = not en_bloque
                continue
            if en_bloque:
                continue
            limpia = CODIGO_INLINE_RE.sub("", linea)
            destinos = ENLACE_RE.findall(limpia) + REFERENCIA_RE.findall(limpia)
            for destino in destinos:
                if destino_roto(ruta, destino):
                    hallazgos.append(f"{rel(ruta, root)}:{numero}: enlace roto: {destino}")
    return hallazgos


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="detecta enlaces relativos rotos en los .md")
    ap.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parent.parent),
                    help="raíz del repo (por defecto, la de este script)")
    root = Path(ap.parse_args(argv).root).resolve()
    hallazgos = enlaces_rotos(root)
    for hallazgo in hallazgos:
        print(hallazgo)
    if hallazgos:
        print(f"ROTO: {len(hallazgos)} hallazgos")
        return 1
    print("OK: sin enlaces rotos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
