"""Contrato de `gns3lab lab`, probado sin servidor GNS3."""
from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CLI_PATH = REPO / "cli" / "gns3lab"
EJEMPLO = REPO / "examples" / "lab-ejemplo.yaml"
LOADER = SourceFileLoader("gns3lab_labtests", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)

ACCIONES = ("validate", "plan", "diff", "apply", "verify", "export")
HANDLERS_BASE = (
    "servers", "status", "up", "down", "test", "export", "import", "fix",
    "port", "compute", "stats", "symbols", "appliances", "images", "templates",
    "snap", "template", "console", "capture", "exec", "shot", "key", "type",
    "mon", "new", "node", "upload", "draw", "link", "doctor", "examen", "pf",
    "verify", "project", "gns3vm", "notify", "symbol", "iou-license", "server",
    "emulator", "nio", "capture-port", "all", "disk", "vm", "watch", "version-v1",
)


def _handler_names() -> list[str]:
    arbol = ast.parse(CLI_PATH.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Assign):
            continue
        if not any(isinstance(destino, ast.Name) and destino.id == "handlers"
                   for destino in nodo.targets):
            continue
        if isinstance(nodo.value, ast.Dict):
            return [clave.value for clave in nodo.value.keys
                    if isinstance(clave, ast.Constant)]
    raise AssertionError("cli/gns3lab no declara el dict `handlers`")


requires_lab = pytest.mark.skipif(
    "lab" not in _handler_names() or not hasattr(cli, "cmd_lab"),
    reason="BRIEF-dclcli pendiente: falta el subcomando lab y su handler",
)


@pytest.fixture
def run_main(monkeypatch, tmp_path):
    """Aísla la configuración para que ninguna prueba toque la del usuario."""
    conf_path = tmp_path / "gns3lab.json"
    conf_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cli, "CONF", conf_path)
    monkeypatch.setattr(cli, "load_conf", lambda: {
        "servers": {},
        "default_server": "local",
    })

    def run(argv):
        monkeypatch.setattr(sys, "argv", ["gns3lab", *argv])
        return cli.main()

    return run


@requires_lab
def test_lab_help_incluye_las_seis_acciones():
    proc = subprocess.run(
        [sys.executable, str(CLI_PATH), "lab", "--help"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    lineas = [line.strip() for line in proc.stdout.splitlines()]
    for accion in ACCIONES:
        assert any(linea.startswith(accion + " ") for linea in lineas)


@requires_lab
def test_lab_validate_json_acepta_el_ejemplo(run_main, capsys):
    rc = run_main(["lab", "validate", "--spec", str(EJEMPLO), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["ok"] is True


@requires_lab
def test_lab_apply_sin_yes_no_ejecuta_nada(run_main, monkeypatch, tmp_path, capsys):
    topologia = tmp_path / "topologia.json"
    topologia.write_text(json.dumps({
        "project": "lab-ejemplo",
        "nodes": [],
        "links": [],
    }), encoding="utf-8")

    def prohibido(*_args, **_kwargs):
        raise AssertionError("lab apply sin --yes no debe lanzar procesos")

    monkeypatch.setattr(subprocess, "run", prohibido)
    monkeypatch.setattr(cli, "_core_client", prohibido)
    monkeypatch.setattr(cli, "Server", prohibido)

    rc = run_main([
        "lab", "apply", "--spec", str(EJEMPLO),
        "--topology", str(topologia), "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["ok"] is False
    assert payload["data"]["plan"]


@requires_lab
def test_lab_apply_con_topologia_idempotente(run_main, monkeypatch, tmp_path, capsys):
    topologia = tmp_path / "topologia.json"
    topologia.write_text(json.dumps({
        "project": "lab-ejemplo",
        "nodes": [
            {"name": "pc1", "template": "VPCS"},
            {"name": "pc2", "template": "VPCS"},
            {"name": "sw1", "template": "Ethernet switch"},
        ],
        "links": [
            {"ends": [
                {"node": "pc1", "adapter": 0, "port_number": 0},
                {"node": "sw1", "adapter": 0, "port_number": 0},
            ]},
            {"ends": [
                {"node": "pc2", "adapter": 0, "port_number": 0},
                {"node": "sw1", "adapter": 1, "port_number": 0},
            ]},
        ],
    }), encoding="utf-8")

    def prohibido(*_args, **_kwargs):
        raise AssertionError("lab apply local no debe construir un cliente GNS3")

    monkeypatch.setattr(cli, "_core_client", prohibido)
    monkeypatch.setattr(cli, "Server", prohibido)

    rc = run_main([
        "lab", "apply", "--spec", str(EJEMPLO),
        "--topology", str(topologia), "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["data"]["plan"] == []
    assert payload["data"]["yes"] is False


@requires_lab
def test_lab_apply_sin_topologia_consulta_y_acepta_proyecto_inexistente(
    run_main, monkeypatch, capsys
):
    llamadas = []

    class Cliente:
        def alive(self):
            llamadas.append("alive")
            return True

        def projects(self):
            llamadas.append("projects")
            return []

        def resolve_project(self, _project):
            raise AssertionError("debe comprobar la existencia exacta antes de resolver")

    monkeypatch.setattr(cli, "Server", lambda *_args: object())
    monkeypatch.setattr(cli, "_core_client", lambda _server: Cliente())

    def prohibido(*_args, **_kwargs):
        raise AssertionError("lab apply sin --yes no debe lanzar procesos")

    monkeypatch.setattr(subprocess, "run", prohibido)

    rc = run_main(["lab", "apply", "--spec", str(EJEMPLO), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert llamadas == ["alive", "projects"]
    assert any("new lab-ejemplo" in cmd for cmd in payload["data"]["plan"])
    assert any("up lab-ejemplo" in cmd for cmd in payload["data"]["plan"])


@requires_lab
def test_lab_apply_sin_topologia_proyecto_vacio_no_arranca(
    run_main, monkeypatch, capsys
):
    class Cliente:
        def alive(self):
            return True

        def projects(self):
            return [{"project_id": "pid-1", "name": "lab-ejemplo"}]

        def nodes(self, _pid):
            return []

        def links(self, _pid):
            return []

    monkeypatch.setattr(cli, "Server", lambda *_args: object())
    monkeypatch.setattr(cli, "_core_client", lambda _server: Cliente())

    rc = run_main(["lab", "apply", "--spec", str(EJEMPLO), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert any("node add" in cmd for cmd in payload["data"]["plan"])
    assert not any("new lab-ejemplo" in cmd for cmd in payload["data"]["plan"])
    assert not any("up lab-ejemplo" in cmd for cmd in payload["data"]["plan"])


@requires_lab
def test_lab_diff_con_topologia_local_no_habla_con_el_servidor(
    run_main, monkeypatch, tmp_path, capsys
):
    topologia = tmp_path / "topologia.json"
    topologia.write_text(json.dumps({
        "project": "lab-ejemplo",
        "nodes": [],
        "links": [],
    }), encoding="utf-8")

    def prohibido(*_args, **_kwargs):
        raise AssertionError("lab diff local no debe construir un cliente GNS3")

    monkeypatch.setattr(cli, "_core_client", prohibido)
    monkeypatch.setattr(cli, "Server", prohibido)

    rc = run_main([
        "lab", "diff", "--spec", str(EJEMPLO),
        "--topology", str(topologia), "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["ok"] is True
    assert payload["action"] == "diff"
    assert len(payload["data"]["crear_nodos"]) == 3


@requires_lab
def test_registro_de_handlers_conserva_el_orden_existente():
    nombres = _handler_names()

    assert nombres.count("lab") == 1
    assert [nombre for nombre in nombres if nombre != "lab"] == list(HANDLERS_BASE)
