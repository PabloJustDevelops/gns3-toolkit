"""Contrato de la CLI tras la optimización de arranque.

Cubre lo que un agente necesita para no adivinar: --json con las mismas claves
en éxito y error, ayuda de una línea por comando y ausencia de secretos en la
salida.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

CLI_PATH = Path(__file__).resolve().parents[1] / "cli" / "gns3lab"
LOADER = SourceFileLoader("gns3lab_optimization_tests", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)


def _comandos() -> set[str]:
    """Nombres del dict `handlers`, igual que los cuenta scripts/verify.py."""
    arbol = ast.parse(CLI_PATH.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "handlers" for t in nodo.targets):
            continue
        if isinstance(nodo.value, ast.Dict):
            return {k.value for k in nodo.value.keys if isinstance(k, ast.Constant)}
    raise AssertionError("cli/gns3lab no declara el dict `handlers`")


@pytest.fixture
def run_main(monkeypatch, tmp_path):
    """Aísla la configuración y deja sustituir el handler de `status`."""
    conf_path = tmp_path / "gns3lab.json"
    conf_path.write_text("{}")
    monkeypatch.setattr(cli, "CONF", conf_path)
    monkeypatch.setattr(cli, "load_conf", lambda: {"servers": {},
                                                   "default_server": "local"})

    def run(argv, handler):
        monkeypatch.setattr(sys, "argv", ["gns3lab", *argv])
        monkeypatch.setattr(cli, "cmd_status", handler)
        return cli.main()

    return run


def _claves(payload: dict) -> set[str]:
    return set(payload)


def test_json_exito_y_error_comparten_las_mismas_claves(run_main, capsys):
    def exito(args, conf):
        print("servidor local: OK")
        return 0

    rc_ok = run_main(["--json", "status"], exito)
    ok = json.loads(capsys.readouterr().out)

    def fallo(args, conf):
        print("parcial")
        raise RuntimeError("no puedo conectar con el servidor: revisa --server")

    rc_error = run_main(["--json", "status"], fallo)
    capturado = capsys.readouterr()
    error = json.loads(capturado.out)

    assert rc_ok == 0 and rc_error == 1
    assert _claves(ok) == _claves(error) == {"cmd", "ok", "output"}
    assert ok["ok"] is True and error["ok"] is False
    assert ok["cmd"] == error["cmd"] == "status"
    assert "revisa --server" in error["output"]
    # El detalle técnico queda en stderr; stdout es JSON parseable.
    assert "RuntimeError" in capturado.err


def test_json_no_reemite_json_parcial_de_un_handler_que_falla(run_main, capsys):
    def fallo(args, conf):
        print('{"ok": true, "output": "a medias"}')
        raise ValueError("fallo después de imprimir")

    rc = run_main(["--json", "status"], fallo)
    capturado = capsys.readouterr()
    payload = json.loads(capturado.out)

    assert rc == 1
    assert _claves(payload) == {"cmd", "ok", "output"}
    assert payload["ok"] is False
    assert "a medias" in payload["output"]
    assert "fallo después de imprimir" in payload["output"]


def test_ayuda_de_cada_comando_es_una_linea_que_dice_que_hace():
    entorno = {**os.environ, "COLUMNS": "240"}
    proc = subprocess.run([sys.executable, str(CLI_PATH), "--help"],
                          capture_output=True, text=True, env=entorno)
    assert proc.returncode == 0, proc.stderr

    ayudas = {}
    for linea in proc.stdout.splitlines():
        partes = linea.split(None, 1)
        if len(partes) == 2 and linea.startswith("    ") and not linea[4].isspace():
            nombre, texto = partes[0], partes[1].strip()
            if nombre in _comandos():
                ayudas[nombre] = texto

    faltan = _comandos() - set(ayudas)
    assert not faltan, f"comandos sin texto de ayuda: {sorted(faltan)}"
    for nombre, texto in ayudas.items():
        assert len(texto) >= 15, f"{nombre}: ayuda demasiado corta: {texto!r}"
        assert "\n" not in texto
        assert " " in texto, f"{nombre}: la ayuda debe describir el comando"
        assert not texto.endswith("."), f"{nombre}: quita el punto final"


def test_ayuda_de_pf_detect_muestra_sus_flags_reales():
    proc = subprocess.run([sys.executable, str(CLI_PATH), "pf", "detect", "--help"],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "--project" in proc.stdout and "--node" in proc.stdout
    assert "--json" in proc.stdout


def test_help_no_lee_la_config_ni_filtra_sus_valores(monkeypatch, capsys, tmp_path):
    """--help debe salir antes de leer la configuración (secretos incluidos)."""
    conf_path = tmp_path / "gns3lab.json"
    conf_path.write_text(json.dumps({
        "servers": {"local": {"url": "http://127.0.0.1:3080", "auth": "secreto-config"}},
        "default_server": "local",
    }))
    lecturas: list[bool] = []
    monkeypatch.setattr(cli, "CONF", conf_path)
    monkeypatch.setattr(cli, "load_conf",
                        lambda: lecturas.append(True) or {"default_server": "local"})
    monkeypatch.setattr(sys, "argv", ["gns3lab", "--help"])

    with pytest.raises(SystemExit) as salida:
        cli.main()

    capturado = capsys.readouterr()
    assert salida.value.code == 0
    assert lecturas == []
    assert "secreto-config" not in capturado.out + capturado.err


def test_json_no_filtra_el_valor_de_una_credencial(monkeypatch, capsys, tmp_path):
    secreto = "s3cr3t-que-no-debe-salir"
    monkeypatch.setenv("PFSENSE_PASSWORD", secreto)
    monkeypatch.setenv("PFSENSE_PORT", "no-es-un-puerto")
    monkeypatch.delenv("PFSENSE_HOST", raising=False)
    conf_path = tmp_path / "gns3lab.json"
    conf_path.write_text("{}")
    monkeypatch.setattr(cli, "CONF", conf_path)
    monkeypatch.setattr(cli, "load_conf", lambda: {"servers": {},
                                                   "default_server": "local"})
    monkeypatch.setattr(sys, "argv", ["gns3lab", "--json", "pf", "status"])

    rc = cli.main()
    capturado = capsys.readouterr()

    assert rc == 1
    assert json.loads(capturado.out)["ok"] is False
    assert secreto not in capturado.out
    assert secreto not in capturado.err
    assert "PFSENSE_PORT" in capturado.err
