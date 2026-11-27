"""Regresiones del carril fix-cli-json: JSON limpio, borrados confirmados y errores visibles."""
from __future__ import annotations

import importlib.util
import json
import socket
import sys
from argparse import Namespace
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

import pytest

CLI_PATH = Path(__file__).resolve().parents[1] / "cli" / "gns3lab"
LOADER = SourceFileLoader("gns3lab_fixjson", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)

CONF = {
    "servers": {"local": {"url": "http://127.0.0.1:3080", "auth": None}},
    "default_server": "local",
}


def _server(_name, _conf):
    return SimpleNamespace(auth=None)


def test_lab_apply_json_manda_el_progreso_a_stderr(monkeypatch, tmp_path, capsys):
    spec = tmp_path / "spec.yaml"
    topo = tmp_path / "topo.json"
    topo.write_text(json.dumps({"project": "lab-ejemplo", "nodes": [], "links": []}),
                    encoding="utf-8")

    class FakeLab:
        def leer(self, _ruta):
            return {"project": "lab-ejemplo", "nodes": [], "links": []}

        def validar(self, _datos):
            return []

        def normalizar(self, datos):
            return datos

        def plan(self, _deseado, _actual, _server):
            return []

        def aplicar_deseado(self, _deseado, _actual, _server, yes):
            assert yes is True
            print("$ gns3lab node add fw1")
            print("lab-ejemplo: aplicado (1 órdenes)")
            return 0

    monkeypatch.setattr(cli, "_lab_module", lambda: FakeLab())
    args = Namespace(lab_action="apply", spec=str(spec), topology=str(topo),
                     yes=True, server="local", project=None, json=False,
                     lab_json=True, global_json=False)

    rc = cli.cmd_lab(args, CONF)
    salida = capsys.readouterr()

    assert rc == 0
    payload = json.loads(salida.out)
    assert payload["ok"] is True
    assert payload["data"]["rc"] == 0
    assert "$ gns3lab node add fw1" in salida.err
    assert "aplicado" in salida.err


def test_all_json_devuelve_un_solo_objeto(monkeypatch, capsys):
    class FakeCore:
        def resolve_project(self, _needle):
            return {"project_id": "p1", "name": "lab"}

        def ensure_open(self, _pid):
            return None

        def nodes_action(self, _pid, _action):
            return 200, {}

        def nodes(self, _pid):
            return [{"status": "started"}, {"status": "stopped"}]

    monkeypatch.setattr(cli, "Server", _server)
    monkeypatch.setattr(cli, "_core_client", lambda _s: FakeCore())
    args = Namespace(server="local", project=None, action="start", yes=True,
                     json=True, global_json=False)

    rc = cli.cmd_all(args, CONF)
    salida = capsys.readouterr()

    assert rc == 0
    payload = json.loads(salida.out)
    assert payload["project"] == "lab"
    assert payload["action"] == "start"
    assert payload["states"] == {"started": 1, "stopped": 1}


def test_watch_json_no_escribe_el_resumen_en_stdout(monkeypatch, capsys):
    class FakeSock:
        def settimeout(self, _timeout):
            return None

        def close(self):
            return None

    eventos = iter([('{"action":"node.started","event":{}}', b"")])

    def _frame(_sock, _pending):
        try:
            return next(eventos)
        except StopIteration:
            raise socket.timeout()

    class FakeCore:
        def notifications_ws_url(self, _pid):
            return "ws://127.0.0.1:3080/notifications"

    monkeypatch.setattr(cli, "Server", _server)
    monkeypatch.setattr(cli, "_core_client", lambda _s: FakeCore())
    monkeypatch.setattr(cli, "_ws_open", lambda *_a, **_k: (FakeSock(), b""))
    monkeypatch.setattr(cli, "_ws_frame", _frame)
    args = Namespace(server="local", project=None, seconds=1,
                     json=True, global_json=False)

    rc = cli.cmd_watch(args, CONF)
    salida = capsys.readouterr()

    assert rc == 0
    assert json.loads(salida.out) == {"action": "node.started", "event": {}}
    assert "1 evento(s)" in salida.err


def test_vm_vms_json_emite_un_solo_documento(monkeypatch, capsys):
    class FakeCore:
        def virtualbox_vms(self):
            return 200, {"vms": ["vb1"]}

        def vmware_vms(self):
            return 200, {"vms": ["vm1"]}

    monkeypatch.setattr(cli, "Server", _server)
    monkeypatch.setattr(cli, "_core_client", lambda _s: FakeCore())
    args = Namespace(server="local", action="vms", engine=None, set=[],
                     json=True, global_json=False)

    rc = cli.cmd_vm(args, CONF)
    salida = capsys.readouterr()

    assert rc == 0
    assert json.loads(salida.out) == {
        "virtualbox": {"vms": ["vb1"]},
        "vmware": {"vms": ["vm1"]},
    }


class FakeDeleteCore:
    def __init__(self):
        self.deleted = []

    def resolve_project(self, _needle):
        return {"project_id": "p1", "name": "lab"}

    def ensure_open(self, _pid):
        return None

    def snapshots(self, _pid):
        return [{"snapshot_id": "snap-1", "name": "s1"}]

    def snapshot_delete(self, _pid, sid):
        self.deleted.append(sid)
        return 204, {}

    def find_node(self, _pid, node):
        return {"node_id": "n1", "name": node}

    def delete(self, path, **_kw):
        self.deleted.append(path)
        return 204, {}

    def drawings(self, _pid):
        return [{"drawing_id": "draw-1", "x": 0, "y": 0, "svg": "<svg/>"}]

    def drawing_delete(self, _pid, did):
        self.deleted.append(did)
        return 204, {}

    def json_list_or_die(self, _path, _what):
        return [{"link_id": "link-1"}]

    def link_delete(self, _pid, lid):
        self.deleted.append(lid)
        return 204, {}


@pytest.mark.parametrize("handler,args,fragment", [
    ("cmd_snap", Namespace(action="delete", name="s1", project=None,
                           server="local", yes=False), "snapshot"),
    ("cmd_node", Namespace(action="rm", node="R1", project=None,
                           server="local", yes=False), "nodo"),
    ("cmd_draw", Namespace(text=["rm", "draw-1"], project=None,
                           server="local", set=[], yes=False), "nota"),
    ("cmd_link", Namespace(action="rm", nodes=["link-1"], project=None,
                           server="local", set=[], yes=False), "enlace"),
])
def test_borrados_exigen_confirmacion(monkeypatch, handler, args, fragment):
    fake = FakeDeleteCore()
    vistos = []
    monkeypatch.setattr(cli, "Server", _server)
    monkeypatch.setattr(cli, "_core_client", lambda _s: fake)
    monkeypatch.setattr(cli, "_confirm",
                        lambda _args, what: vistos.append(what) or False)

    rc = getattr(cli, handler)(args, CONF)

    assert rc == 1
    assert fake.deleted == []
    assert any(fragment in texto.lower() for texto in vistos), vistos


@pytest.mark.skipif(getattr(cli, "core", None) is None,
                    reason="falta gns3core para comprobar ConsoleError")
def test_exec_cierra_la_consola_al_enviar_sin_traceback(monkeypatch, capsys):
    class FakeConsole:
        def wait_ready(self, timeout):
            return {"prompt": ">", "ready": True}

        def run_many(self, *_a, **_kw):
            raise cli.core.ConsoleError("telnet cerrado al enviar")

        def close(self):
            return None

    nodo = {"node_id": "n1", "name": "R1", "status": "started"}
    monkeypatch.setattr(cli, "_core_target",
                        lambda *_a: (object(), {"project_id": "p1", "name": "lab"}, nodo))
    monkeypatch.setattr(cli.core, "console_for", lambda *_a: FakeConsole())
    args = Namespace(server="local", node="R1", commands=["show ip"], project=None,
                     ready_timeout=1, expect=None, idle=0, timeout=1, answers=[])

    rc = cli.cmd_exec(args, CONF)
    salida = capsys.readouterr()

    assert rc == 1
    assert "telnet cerrado al enviar" in salida.err
    assert "Traceback" not in salida.err


def test_lab_modo_humano_muestra_el_mensaje_de_error(monkeypatch, capsys):
    class FakeLab:
        def leer(self, _ruta):
            raise ValueError("spec rota: falta project")

    monkeypatch.setattr(cli, "_lab_module", lambda: FakeLab())
    args = Namespace(lab_action="validate", spec="no-importa.yaml", server="local",
                     project=None, json=False, lab_json=False, global_json=False)

    rc = cli.cmd_lab(args, CONF)
    salida = capsys.readouterr()

    assert rc == 1
    assert "spec rota: falta project" in salida.out
