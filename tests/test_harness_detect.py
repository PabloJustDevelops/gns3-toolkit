"""Detección de harnesses sin red, sin instalación y sin lanzar prompts.

Los dobles sustituyen `shutil.which` y `subprocess.run`: la suite no necesita
que los cinco harnesses estén instalados en la máquina que la ejecuta.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "scripts" / "harness_detect.py"
DOC = RAIZ / "docs" / "HARNESSES.md"
NOMBRES = ("cmdc", "opencode", "hermes", "freebuff", "codex")
CLAVES = {"harness", "path", "version", "command", "headless", "notes"}


class Proc:
    """Resultado mínimo de `subprocess.run`."""

    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def cargar():
    spec = importlib.util.spec_from_file_location("harness_detect", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def doblar(monkeypatch, modulo, salida="1.2.3", error=None):
    monkeypatch.setattr(modulo.shutil, "which", lambda nombre: f"/bin/{nombre}")

    def falso_run(*args, **kwargs):
        if error is not None:
            raise error
        return Proc(salida)

    monkeypatch.setattr(modulo.subprocess, "run", falso_run)


def test_forma_del_json_y_orden_de_los_cinco(monkeypatch, capsys):
    modulo = cargar()
    doblar(monkeypatch, modulo)

    assert modulo.main(["--json"]) == 0

    data = json.loads(capsys.readouterr().out)
    assert data["exit_code"] == 0
    assert [entrada["harness"] for entrada in data["harnesses"]] == list(NOMBRES)
    for entrada in data["harnesses"]:
        assert set(entrada) == CLAVES
        assert entrada["path"] == f"/bin/{entrada['harness']}"
        assert entrada["version"] == "1.2.3"
        assert isinstance(entrada["headless"], bool)
        assert entrada["command"]
        assert entrada["notes"]


def test_harness_ausente_devuelve_exit_code_1(monkeypatch, capsys):
    modulo = cargar()
    monkeypatch.setattr(
        modulo.shutil, "which", lambda nombre: None if nombre == "freebuff" else f"/bin/{nombre}"
    )
    monkeypatch.setattr(modulo.subprocess, "run", lambda *a, **k: Proc("1.2.3"))

    assert modulo.main(["--json"]) == 1

    data = json.loads(capsys.readouterr().out)
    assert data["exit_code"] == 1
    assert data["missing"] == ["freebuff"]
    ausente = next(e for e in data["harnesses"] if e["harness"] == "freebuff")
    assert ausente["path"] is None
    assert ausente["version"] is None
    assert "no instalado" in ausente["notes"]
    assert ausente["headless"] is False


def test_timeout_de_version_no_rompe_la_deteccion(monkeypatch, capsys):
    modulo = cargar()
    doblar(
        monkeypatch,
        modulo,
        error=subprocess.TimeoutExpired(cmd=["cmdc", "--version"], timeout=5),
    )

    assert modulo.main(["--json"]) == 0

    data = json.loads(capsys.readouterr().out)
    entrada = data["harnesses"][0]
    assert entrada["path"] == "/bin/cmdc"
    assert entrada["version"] is None
    assert "tiempo" in entrada["notes"]


def test_version_no_parseable_se_reporta(monkeypatch, capsys):
    modulo = cargar()
    doblar(monkeypatch, modulo, salida="salida sin número de versión")

    assert modulo.main(["--json"]) == 0

    data = json.loads(capsys.readouterr().out)
    entrada = data["harnesses"][0]
    assert entrada["version"] is None
    assert "no parseable" in entrada["notes"]


def test_version_con_prefijo_se_extrae(monkeypatch):
    modulo = cargar()
    doblar(monkeypatch, modulo, salida="opencode v2.4.1")

    entrada = modulo.detect("opencode")

    assert entrada["version"] == "2.4.1"


def test_version_multilinea_toma_la_primera(monkeypatch):
    modulo = cargar()
    doblar(
        monkeypatch,
        modulo,
        salida="Hermes Agent v0.23.4 (2026.9.24) · stable\nPython: 3.14.9\n",
    )

    entrada = modulo.detect("hermes")

    assert entrada["version"] == "0.23.4"


def test_la_matriz_documenta_los_cinco():
    texto = DOC.read_text(encoding="utf-8")
    for nombre in NOMBRES:
        assert re.search(rf"^\|\s*\[?{nombre}\b", texto, re.M), nombre
    assert "scripts/harness_detect.py" in texto
    assert "freebuff" in texto and "sin modo headless" in texto
