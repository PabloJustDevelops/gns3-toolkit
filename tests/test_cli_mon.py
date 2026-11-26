"""Contrato de `gns3lab mon`, probado sin servidor GNS3 ni QEMU real."""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

import gns3core

REPO = Path(__file__).resolve().parents[1]
CLI_PATH = REPO / "cli" / "gns3lab"
LOADER = SourceFileLoader("gns3lab_montests", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)


@pytest.fixture
def run_main(monkeypatch, tmp_path):
    """Aísla la configuración para que ninguna prueba toque la del usuario."""
    conf_path = tmp_path / "gns3lab.json"
    conf_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cli, "CONF", conf_path)
    monkeypatch.setattr(cli, "load_conf", lambda: {
        "servers": {"local": {"url": "http://127.0.0.1:1", "auth": None}},
        "default_server": "local",
    })

    def run(argv):
        monkeypatch.setattr(sys, "argv", ["gns3lab", *argv])
        return cli.main()

    return run


@pytest.fixture
def dobles(monkeypatch):
    """Sustituye el cliente REST y el monitor HMP por dobles sin red."""
    llamadas = {"projects": [], "nodes": [], "for_node": [], "commands": []}

    class Cliente:
        def __init__(self, _url, _auth, _matcher, _name):
            pass

        def resolve_project(self, project):
            llamadas["projects"].append(project)
            return {"project_id": "pid-1", "name": "lab"}

        def ensure_open(self, project_id):
            assert project_id == "pid-1"

        def find_node(self, project_id, node):
            llamadas["nodes"].append((project_id, node))
            return {
                "node_id": "node-1",
                "name": node,
                "node_type": "qemu",
                "properties": {"hda_disk_image": "disko.qcow2"},
            }

    class Monitor:
        def __init__(self):
            self.cerrado = False
            llamadas["monitor"] = self

        @classmethod
        def for_node(cls, **kwargs):
            llamadas["for_node"].append(kwargs)
            return cls()

        def run(self, command):
            llamadas["commands"].append(command)
            return {"output": "VM status: running", "error": None}

        def close(self):
            self.cerrado = True

    monkeypatch.setattr(gns3core, "Client", Cliente)
    monkeypatch.setattr(gns3core, "QemuMonitor", Monitor)
    return llamadas


def test_mon_no_colisiona_con_cmd_y_envia_una_cadena(
    run_main, dobles, monkeypatch, capsys
):
    handler = cli.cmd_mon

    def comprobar_args(args, conf):
        assert args.cmd == "mon"
        assert args.command == ["info", "status"]
        return handler(args, conf)

    monkeypatch.setattr(cli, "cmd_mon", comprobar_args)

    rc = run_main(["mon", "qemu1", "info", "status", "-p", "lab"])

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    assert dobles["projects"] == ["lab"]
    assert dobles["nodes"] == [("pid-1", "qemu1")]
    assert dobles["for_node"] == [{
        "node_id": "node-1",
        "disk": "disko.qcow2",
    }]
    assert dobles["commands"] == ["info status"]
    assert dobles["monitor"].cerrado is True
    assert json.loads(captured.out) == {
        "output": "VM status: running",
        "error": None,
    }


def test_mon_con_json_global_devuelve_un_objeto_parseable(
    run_main, dobles, capsys
):
    rc = run_main(["--json", "mon", "qemu1", "info", "status", "-p", "lab"])

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    assert dobles["commands"] == ["info status"]
    assert isinstance(json.loads(captured.out), dict)


def test_ningun_subparser_declara_un_posicional_cmd():
    arbol = ast.parse(CLI_PATH.read_text(encoding="utf-8"))
    declaraciones = [
        nodo.lineno
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Attribute)
        and nodo.func.attr == "add_argument"
        and nodo.args
        and isinstance(nodo.args[0], ast.Constant)
        and nodo.args[0].value == "cmd"
    ]

    assert declaraciones == []
