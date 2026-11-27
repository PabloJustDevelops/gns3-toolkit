#!/usr/bin/env python3
"""Guard de deriva entre docs, skill y código. Solo lectura, sin servidor.

Los conteos se sacan del AST del código; las cifras escritas a mano en la
documentación se contrastan con ellos. No modifica ningún fichero.
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

CODIGO = ("gns3core.py", "gns3_mcp_server.py", "cli/gns3lab")
DOCUMENTOS = ("AGENTS.md", "README.md", "PROJECT.md", "docs/GUI-PORTADA.md")
OBLIGATORIOS = CODIGO + ("README.md", "PROJECT.md", "docs/GUI-PORTADA.md", "scripts/install.sh")
SKILL_REAL = Path.home() / ".hermes/skills/devops/gns3-lab-automation/SKILL.md"
SKILL_REPO = Path("skill-sync/SKILL.md")

# Las secciones históricas cuentan lo que era cierto en su tanda, no el estado actual.
HISTORIA_RE = re.compile(r"hito|bitácora|tanda|pasada|históri", re.I)
CIFRA_RE = re.compile(r"(?<![\w/.-])(\d{1,3})\s*(áreas|area|areas|tools|comandos|subcomandos)\b", re.I)
TOOL_RE = re.compile(r"\bgns3_[a-z0-9_]+\b")
CLI_RE = re.compile(r"\bgns3lab\s+([a-z][a-z0-9-]*)")
ENLACE_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)")
SECRETO_RE = re.compile(r"\b(password|api_key|apikey|token|secret)\b\s*[:=]\s*['\"]([^'\"]{1,80})['\"]", re.I)
SALTAR_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".coverage"}


class LecturaError(Exception):
    """Un fichero obligatorio no se puede leer o analizar."""


def rel(ruta: Path, root: Path) -> str:
    try:
        return str(ruta.relative_to(root))
    except ValueError:
        return str(ruta)


def leer(ruta: Path) -> str:
    try:
        return ruta.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise LecturaError(f"{ruta}: no se puede leer ({exc})") from exc


def _asignacion(node, nombre):
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return any(isinstance(t, ast.Name) and t.id == nombre for t in targets)


def _es_tool(decorador) -> bool:
    if isinstance(decorador, ast.Call):
        decorador = decorador.func
    return (isinstance(decorador, ast.Attribute) and decorador.attr == "tool"
            and isinstance(decorador.value, ast.Name) and decorador.value.id == "mcp")


def symbols_code(root: Path) -> dict[str, set[str]]:
    """Nombres reales de comandos, tools y áreas, extraídos del código."""
    cli = ast.parse(leer(root / "cli/gns3lab"), filename="cli/gns3lab")
    handlers = [n.value for n in ast.walk(cli)
                if isinstance(n, (ast.Assign, ast.AnnAssign)) and _asignacion(n, "handlers")
                and isinstance(n.value, ast.Dict)]
    if not handlers:
        raise LecturaError("cli/gns3lab: no se encuentra el dict `handlers`")
    comandos = {k.value for k in handlers[-1].keys if isinstance(k, ast.Constant)}

    mcp = ast.parse(leer(root / "gns3_mcp_server.py"), filename="gns3_mcp_server.py")
    tools = {n.name for n in ast.walk(mcp)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             and any(_es_tool(d) for d in n.decorator_list)}

    core = ast.parse(leer(root / "gns3core.py"), filename="gns3core.py")
    areas = [n.value for n in ast.walk(core)
             if isinstance(n, (ast.Assign, ast.AnnAssign)) and _asignacion(n, "API_V2_MAP")
             and isinstance(n.value, ast.Dict)]
    if not areas:
        raise LecturaError("gns3core.py: no se encuentra `API_V2_MAP`")
    return {"comandos": comandos, "tools": tools, "areas": set(ast.literal_eval(areas[-1]))}


def count_all(root: Path) -> dict[str, int]:
    """Cifras reales; también la usa la suite de tests para generar su fixture."""
    return {clave: len(valores) for clave, valores in symbols_code(root).items()}


def _cifras_declaradas(ruta: Path, root: Path, reales: dict[str, int]) -> list[str]:
    hallazgos = []
    historico = False
    # mcp-README.orig.md es una instantánea de otro proyecto, no una declaración de este.
    if ruta.name.endswith(".orig.md"):
        return hallazgos
    for numero, linea in enumerate(leer(ruta).splitlines(), 1):
        if linea.lstrip().startswith("#"):
            historico = bool(HISTORIA_RE.search(linea))
            continue
        if historico:
            continue
        for texto, termino in CIFRA_RE.findall(linea):
            clave = "tools" if termino.lower() == "tools" else (
                "areas" if termino.lower().startswith("area") or termino.lower() == "áreas" else "comandos")
            valor = int(texto)
            if valor != reales[clave]:
                hallazgos.append(
                    f"{rel(ruta, root)}:{numero}: declara {valor} {termino}, "
                    f"el código tiene {reales[clave]} {clave}")
    return hallazgos


def _en_curso(ruta: Path, root: Path, simbolos: dict[str, set[str]]) -> list[str]:
    hallazgos = []
    for numero, linea in enumerate(leer(ruta).splitlines(), 1):
        if "en curso" not in linea.lower():
            continue
        encontrados = set(TOOL_RE.findall(linea)) & simbolos["tools"]
        encontrados.update(set(CLI_RE.findall(linea)) & simbolos["comandos"])
        if encontrados:
            hallazgos.append(
                f"{rel(ruta, root)}:{numero}: «en curso» con símbolo ya existente: "
                + ", ".join(sorted(encontrados)))
    return hallazgos


def _enlaces(root: Path) -> list[str]:
    hallazgos = []
    for ruta in sorted(root.glob("docs/**/*.md")) + sorted(root.glob("skill-sync/**/*.md")):
        for numero, linea in enumerate(leer(ruta).splitlines(), 1):
            for destino in ENLACE_RE.findall(linea):
                destino = destino.split("#", 1)[0].split("?", 1)[0]
                if not destino or re.match(r"^[a-zA-Z][\w+.-]*:|^//", destino):
                    continue
                objetivo = (ruta.parent / destino).resolve()
                if not objetivo.exists():
                    hallazgos.append(f"{rel(ruta, root)}:{numero}: enlace roto: {destino}")
    return hallazgos


def _ficheros_versionados(root: Path) -> list[Path]:
    try:
        proc = subprocess.run(["git", "ls-files", "-z"], cwd=root,
                              capture_output=True, check=False)
    except OSError:
        proc = None
    if proc is not None and proc.returncode == 0 and proc.stdout:
        return [root / nombre for nombre in proc.stdout.decode().split("\0") if nombre]
    return [p for p in root.rglob("*") if p.is_file()
            and not SALTAR_DIRS.intersection(p.relative_to(root).parts)]


def _secretos(root: Path) -> list[str]:
    hallazgos = []
    for ruta in _ficheros_versionados(root):
        partes = ruta.relative_to(root).parts
        # Los tests usan credenciales ficticias deliberadas por contrato.
        if "tests" in partes or SALTAR_DIRS.intersection(partes):
            continue
        try:
            texto = ruta.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for numero, linea in enumerate(texto.splitlines(), 1):
            for clave, literal in SECRETO_RE.findall(linea):
                if literal.lower() in {"changeme", "todo", "xxx", "placeholder"}:
                    continue
                hallazgos.append(
                    f"{rel(ruta, root)}:{numero}: secreto en literal: {clave}=...")
    return hallazgos


def check(root: Path) -> tuple[list[str], dict[str, set[str]]]:
    for nombre in OBLIGATORIOS:
        if not (root / nombre).is_file():
            raise LecturaError(f"{nombre}: fichero obligatorio ausente")
    simbolos = symbols_code(root)
    reales = {clave: len(valores) for clave, valores in simbolos.items()}
    hallazgos = []
    documentos = [root / nombre for nombre in DOCUMENTOS if (root / nombre).is_file()]
    documentos += sorted(root.glob("docs/**/*.md"))
    documentos += [p for p in (SKILL_REAL, root / SKILL_REPO) if p.is_file()]
    for ruta in dict.fromkeys(documentos):
        hallazgos.extend(_cifras_declaradas(ruta, root, reales))
    gui = root / "docs/GUI-PORTADA.md"
    hallazgos.extend(_en_curso(gui, root, simbolos))
    hallazgos.extend(_enlaces(root))
    hallazgos.extend(_secretos(root))
    return hallazgos, simbolos


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="detecta deriva entre docs, skill y código")
    ap.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parent.parent),
                    help="raíz del repo (por defecto, la de este script)")
    root = Path(ap.parse_args(argv).root).resolve()
    try:
        hallazgos, simbolos = check(root)
    except LecturaError as exc:
        print(f"ERROR: {exc}")
        return 2
    print("comandos={comandos} tools={tools} áreas={areas}".format(
        **{k: len(v) for k, v in simbolos.items()}))
    for hallazgo in hallazgos:
        print(hallazgo)
    if hallazgos:
        print(f"DRIFT: {len(hallazgos)} hallazgos")
        return 1
    print("OK: sin deriva")
    return 0


if __name__ == "__main__":
    sys.exit(main())
