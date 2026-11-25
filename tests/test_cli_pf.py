"""Contrato de `gns3lab pf` con API GNS3 falsa y sin SSH real."""
from __future__ import annotations

import importlib.util
import json
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

try:
    import pfsense
except ModuleNotFoundError as exc:
    if exc.name != "pfsense":
        raise
    pfsense = None

CLI_PATH = Path(__file__).resolve().parents[1] / "cli" / "gns3lab"
LOADER = SourceFileLoader("gns3lab_pftests", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)

pytestmark = pytest.mark.skipif(
    not callable(getattr(cli, "cmd_pf", None)) or pfsense is None,
    reason="BRIEF-pfcli/pfcore pendientes: falta cmd_pf o el módulo pfsense.py",
)


@pytest.fixture(autouse=True)
def limpia_entorno_pfsense(monkeypatch):
    for name in ("PFSENSE_HOST", "PFSENSE_USER", "PFSENSE_PASSWORD", "PFSENSE_PORT"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def cli_conf(fake_api, monkeypatch, tmp_path):
    project = {
        "project_id": "11111111-aaaa-bbbb-cccc-000000000001",
        "name": "lab-prueba",
        "status": "opened",
    }
    node = {
        "node_id": "nodo-pfsense",
        "name": "pfSense",
        "node_type": "qemu",
        "properties": {"adapter_type": "e1000"},
        "status": "stopped",
    }
    fake_api.set_projects([project])
    fake_api.route("GET", f"/v2/projects/{project['project_id']}", 200, project)
    fake_api.set_nodes(project["project_id"], [node])
    conf = {
        "servers": {"prueba": {"url": fake_api.url, "auth": None}},
        "default_server": "prueba",
    }
    conf_path = tmp_path / "gns3lab.json"
    conf_path.write_text("{}")
    monkeypatch.setattr(cli, "CONF", conf_path)
    monkeypatch.setattr(cli, "load_conf", lambda: conf)
    return conf


def _run_cli(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["gns3lab", *argv])
    try:
        return cli.main()
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1


def test_pf_detect_sin_credenciales_solo_lee_el_nodo(
    cli_conf, fake_api, monkeypatch, capsys,
):
    def no_ssh(*args, **kwargs):
        raise AssertionError("pf detect no debe ejecutar SSH ni leer credenciales")

    monkeypatch.setattr(pfsense.subprocess, "run", no_ssh)
    monkeypatch.setattr(pfsense.PfSense, "from_env", no_ssh)

    rc = _run_cli(monkeypatch, ["pf", "detect", "-p", "lab-prueba", "--json"])

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["data"]["project"] == "lab-prueba"
    assert payload["data"]["node"] == "pfSense"
    assert payload["data"]["wan"] == "em0"
    assert payload["data"]["lan"] == "em1"
    assert fake_api.requests
    assert all(req["method"] == "GET" for req in fake_api.requests)


def test_pf_status_sin_password_nombra_la_variable_sin_imprimir_valor(
    cli_conf, fake_api, monkeypatch, capsys,
):
    monkeypatch.setenv("PFSENSE_HOST", "host-que-no-se-imprime")
    monkeypatch.setenv("PFSENSE_USER", "usuario-que-no-se-imprime")

    def no_ssh(*args, **kwargs):
        raise AssertionError("falta la contraseña: no debe construir cliente ni ejecutar SSH")

    monkeypatch.setattr(pfsense.PfSense, "from_env", no_ssh)
    monkeypatch.setattr(pfsense.subprocess, "run", no_ssh)

    rc = _run_cli(monkeypatch, ["pf", "status"])

    captured = capsys.readouterr()
    texto = captured.out + captured.err
    assert rc == 1
    assert "PFSENSE_PASSWORD" in texto
    assert "PFSENSE_PASSWORD=" not in texto
    assert "host-que-no-se-imprime" not in texto
    assert "usuario-que-no-se-imprime" not in texto
    assert fake_api.requests == []
