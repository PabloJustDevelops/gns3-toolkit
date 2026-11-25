"""Contrato de `gns3lab node disk-resize`: la CLI pide GB, la API espera MiB."""
from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

CLI_PATH = Path(__file__).resolve().parents[1] / "cli" / "gns3lab"
LOADER = SourceFileLoader("gns3lab_nodetests", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)

pytestmark = pytest.mark.skipif(
    getattr(cli, "core", None) is None,
    reason="falta gns3core: la CLI no puede resolver el nodo",
)

CONF = {
    "servers": {"local": {"url": "http://127.0.0.1:3080", "auth": None}},
    "default_server": "local",
}


class FakeCore:
    def __init__(self):
        self.resize = None

    def resolve_project(self, _needle):
        return {"project_id": "p1", "name": "lab"}

    def ensure_open(self, _pid):
        return None

    def find_node(self, _pid, node):
        return {"node_id": "n1", "name": node}

    def node_resize_disk(self, pid, nid, size, drive="hda"):
        self.resize = (pid, nid, size, drive)
        return 200, {"status": "resized"}


def _args(size):
    return Namespace(server="local", project=None, action="disk-resize",
                     node="R1", size=size, json=False)


def test_disk_resize_convierte_gb_de_la_cli_a_mib_de_la_api(monkeypatch, capsys):
    fake = FakeCore()
    monkeypatch.setattr(cli, "_core_client", lambda _server: fake)

    rc = cli.cmd_node(_args(16.0), CONF)

    assert rc == 0
    assert fake.resize == ("p1", "n1", 16384, "hda")
    assert "16 GB" in capsys.readouterr().out


@pytest.mark.parametrize("size", [0, -1])
def test_disk_resize_rechaza_tamanos_no_positivos(monkeypatch, size):
    fake = FakeCore()
    monkeypatch.setattr(cli, "_core_client", lambda _server: fake)

    with pytest.raises(SystemExit):
        cli.cmd_node(_args(size), CONF)
    assert fake.resize is None
