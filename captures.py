"""Capturas de consola por fase desde el monitor HMP, sin VNC.

Pillow sólo se usa para convertir el PPM que genera QEMU. Si no está, se conserva
la imagen temporal como artefacto y el resultado lo explica; tesseract también es
opcional y su ausencia deja el OCR vacío sin romper la captura.
"""
from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from gns3core import ocr

MAX_FASES = 5
OCR_MAX = 160
PNG_FIRMA = b"\x89PNG\r\n\x1a\n"


def _error_inicial(phase: str, node: str | None, error: str) -> dict:
    return {"ok": False, "phase": phase, "path": None, "ocr": "",
            "node": node, "error": error}


def _validar_fase(phase: str) -> str:
    if not isinstance(phase, str) or not phase.strip():
        raise ValueError("phase: obligatorio y no vacío")
    nombre = phase.strip()
    if nombre in {".", ".."} or any(caracter in nombre for caracter in ("/", "\\", "\0")):
        raise ValueError("phase: no puede contener separadores de ruta")
    return nombre


def _siguiente_numero(outdir: Path) -> int:
    numeros = []
    for ruta in outdir.iterdir():
        coincidencia = re.match(r"^(\d+)-.+\.(?:png|ppm)$", ruta.name,
                                re.IGNORECASE | re.DOTALL)
        if coincidencia:
            numeros.append(int(coincidencia.group(1)))
    return max(numeros, default=0) + 1


def capture_phase(monitor, phase: str, outdir: str, node: str | None = None) -> dict:
    """Captura un framebuffer HMP y devuelve PNG/OCR sin lanzar excepciones."""
    try:
        nombre_fase = _validar_fase(phase)
    except ValueError as exc:
        return _error_inicial(str(phase), node, str(exc))

    try:
        directorio = Path(outdir).expanduser()
        directorio.mkdir(parents=True, exist_ok=True)
        numero = _siguiente_numero(directorio)
    except OSError as exc:
        return _error_inicial(nombre_fase, node, f"no se puede preparar {outdir}: {exc}")

    with tempfile.TemporaryDirectory(prefix="gns3-capture-") as temporal:
        # QemuMonitor.screendump escribe captura.ppm y entrega captura.png ya x2.
        base = Path(temporal) / "captura.png"
        try:
            shot = monitor.screendump(dest=str(base), scale=2)
        except Exception as exc:
            return _error_inicial(nombre_fase, node, f"screendump falló: {exc}")
        if not isinstance(shot, dict):
            return _error_inicial(nombre_fase, node, "screendump devolvió un resultado inválido")
        if shot.get("error"):
            return _error_inicial(nombre_fase, node, str(shot["error"]))

        origen = shot.get("path")
        if not origen:
            return _error_inicial(nombre_fase, node, "screendump no devolvió ruta")
        origen = Path(origen)
        if not origen.is_file():
            return _error_inicial(nombre_fase, node, f"screendump no creó {origen}")

        avisos = []
        try:
            from PIL import Image
        except ImportError as exc:
            try:
                with origen.open("rb") as fichero:
                    firma = fichero.read(len(PNG_FIRMA))
            except OSError as error:
                return _error_inicial(
                    nombre_fase, node, f"no se pudo leer la captura temporal: {error}")
            extension = "png" if firma == PNG_FIRMA else "ppm"
            destino = directorio / f"{numero:02d}-{nombre_fase}.{extension}"
            try:
                shutil.copyfile(origen, destino)
            except OSError as error:
                return _error_inicial(
                    nombre_fase, node, f"no se pudo conservar la captura: {error}")
            ruta = destino
            avisos.append(f"Pillow no disponible ({exc}); se conserva {extension.upper()}")
        else:
            destino = directorio / f"{numero:02d}-{nombre_fase}.png"
            try:
                with Image.open(origen) as imagen:
                    imagen.convert("L").save(destino)
            except Exception as exc:
                return _error_inicial(nombre_fase, node, f"Pillow no pudo convertir la captura: {exc}")
            ruta = destino

    try:
        texto = ocr(str(ruta), psm=4) or ""
    except Exception as exc:
        texto = ""
        avisos.append(f"OCR falló: {exc}")
    if not texto and not shutil.which("tesseract"):
        avisos.append("tesseract no disponible; OCR vacío")

    return {"ok": True, "phase": nombre_fase, "path": str(ruta), "ocr": texto,
            "node": node, "error": "; ".join(avisos) if avisos else None}


def _celda(valor, limite: int | None = None) -> str:
    texto = "-" if valor is None else str(valor)
    texto = " ".join(texto.split())
    if limite is not None and len(texto) > limite:
        texto = texto[:limite - 1] + "…"
    return texto.replace("|", r"\|")


def write_index(entries: list[dict], outdir: str) -> str:
    """Escribe sólo la tabla de capturas y su estado, no un informe largo."""
    directorio = Path(outdir).expanduser()
    directorio.mkdir(parents=True, exist_ok=True)
    lineas = [
        "# Índice de capturas",
        "",
        "| fase | archivo | nodo | OCR |",
        "|---|---|---|---|",
    ]
    for entrada in entries:
        archivo = Path(entrada["path"]).name if entrada.get("path") else "-"
        lineas.append(
            f"| {_celda(entrada.get('phase'))} | {_celda(archivo)} | "
            f"{_celda(entrada.get('node'))} | {_celda(entrada.get('ocr'), OCR_MAX)} |"
        )
    ok = sum(bool(entrada.get("ok")) for entrada in entries)
    fallos = len(entries) - ok
    sustantivo = "fallo" if fallos == 1 else "fallos"
    lineas.extend(["", f"Estado: {ok} OK, {fallos} {sustantivo}"])
    ruta = directorio / "indice.md"
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return str(ruta)


def phases_from_spec(spec: dict) -> list[dict]:
    """Valida y normaliza ``captures``; como máximo cinco fases declarativas."""
    if not isinstance(spec, dict):
        raise ValueError("spec: debe ser un mapa")
    entradas = spec.get("captures")
    if entradas is None:
        return []
    if not isinstance(entradas, list):
        raise ValueError("captures: debe ser una lista")
    if len(entradas) > MAX_FASES:
        raise ValueError(f"captures: máximo {MAX_FASES} fases")

    fases = []
    for i, entrada in enumerate(entradas):
        base = f"captures[{i}]"
        if not isinstance(entrada, dict):
            raise ValueError(f"{base}: debe ser un mapa")
        try:
            phase = _validar_fase(entrada.get("phase"))
        except ValueError as exc:
            detalle = str(exc).removeprefix("phase: ")
            raise ValueError(f"{base}.phase: {detalle}") from exc
        after = entrada.get("after")
        if not isinstance(after, str) or after not in {"apply", "verify"}:
            raise ValueError(f"{base}.after: debe ser 'apply' o 'verify'")
        node = entrada.get("node")
        if node is not None and (not isinstance(node, str) or not node.strip()):
            raise ValueError(f"{base}.node: debe ser texto no vacío o null")
        fases.append({"phase": phase, "after": after,
                      "node": node.strip() if isinstance(node, str) else None})
    return fases
