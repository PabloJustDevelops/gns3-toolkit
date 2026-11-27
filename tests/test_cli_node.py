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


class FakeAddCore:
    def __init__(self):
        self.template = {"template_id": "t1", "name": "NAT", "template_type": "nat",
                         "symbol": ":/symbols/classic/nat.svg"}
        self.available = [
            {"symbol_id": ":/symbols/classic/nat.svg", "filename": "nat.svg"},
            {"symbol_id": ":/symbols/classic/firewall.svg", "filename": "firewall.svg"},
            {"symbol_id": ":/symbols/classic/computer.svg", "filename": "computer.svg"},
        ]
        self.posts = []
        self.puts = []
        self.symbol_reads = 0
        self.put_status = 200
        self.node = {"node_id": "n1", "name": "NAT1", "node_type": "nat",
                     "symbol": self.template["symbol"]}

    def resolve_project(self, _needle):
        return {"project_id": "p1", "name": "lab"}

    def ensure_open(self, _pid):
        return None

    def json_or_die(self, path, _what):
        assert path == "/v2/templates"
        return [self.template]

    def symbols(self):
        self.symbol_reads += 1
        return self.available

    def post(self, path, payload):
        self.posts.append((path, payload))
        return 201, dict(self.node)

    def put(self, path, payload):
        self.puts.append((path, payload))
        if self.put_status not in (200, 201):
            return self.put_status, {"message": "boom"}
        self.node.update(payload)
        return self.put_status, dict(self.node)


def _add_args(symbol=None):
    return Namespace(server="local", project=None, action="add", node=None,
                     template="NAT", name=None, x=0, y=0, json=False,
                     symbol=symbol)


def test_parser_node_add_acepta_symbol(monkeypatch, tmp_path):
    conf_path = tmp_path / "gns3lab.json"
    conf_path.write_text("{}")
    monkeypatch.setattr(cli, "CONF", conf_path)
    monkeypatch.setattr(cli, "load_conf", lambda: CONF)
    visto = {}
    monkeypatch.setattr(cli, "cmd_node", lambda args, _conf: visto.update(vars(args)) or 0)
    monkeypatch.setattr(sys, "argv", [
        "gns3lab", "node", "add", "--template", "NAT",
        "--symbol", ":/symbols/classic/firewall.svg",
    ])

    assert cli.main() == 0
    assert visto["symbol"] == ":/symbols/classic/firewall.svg"


def test_node_add_aplica_symbol_tras_instanciar_la_plantilla(monkeypatch, capsys):
    fake = FakeAddCore()
    monkeypatch.setattr(cli, "_core_client", lambda _server: fake)

    rc = cli.cmd_node(_add_args("firewall.svg"), CONF)

    assert rc == 0
    assert fake.puts == [("/v2/projects/p1/nodes/n1", {"symbol": "firewall.svg"})]
    assert "symbol=firewall.svg" in capsys.readouterr().out


def test_node_add_sin_symbol_deja_el_del_servidor_y_lo_reporta(monkeypatch, capsys):
    fake = FakeAddCore()
    fake.node["symbol"] = ":/symbols/classic/computer.svg"
    monkeypatch.setattr(cli, "_core_client", lambda _server: fake)

    rc = cli.cmd_node(_add_args(), CONF)

    assert rc == 0
    assert fake.puts == []
    assert fake.symbol_reads == 0
    assert "symbol=:/symbols/classic/computer.svg" in capsys.readouterr().out


def test_node_add_con_symbol_inexistente_no_crea_nodo(monkeypatch, capsys):
    fake = FakeAddCore()
    monkeypatch.setattr(cli, "_core_client", lambda _server: fake)

    rc = cli.cmd_node(_add_args("no-existe.svg"), CONF)

    assert rc == 1
    assert fake.posts == []
    error = capsys.readouterr().err
    assert "no-existe.svg" in error
    assert ":/symbols/classic/firewall.svg" in error


def test_node_add_si_falla_el_put_identifica_el_nodo_ya_creado(monkeypatch, capsys):
    fake = FakeAddCore()
    fake.put_status = 500
    monkeypatch.setattr(cli, "_core_client", lambda _server: fake)
    args = _add_args("firewall.svg")
    args.name = "NAT2"

    rc = cli.cmd_node(args, CONF)

    assert rc == 1
    assert len(fake.posts) == 1
    error = capsys.readouterr().err
    assert "nodo n1 creado" in error
    assert "no se pudo configurar" in error
    assert "boom" in error
