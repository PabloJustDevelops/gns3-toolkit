"""Issue #17: pfSense QEMU debe usar telnet por defecto y avisar si usa VNC/SPICE."""
from __future__ import annotations

import importlib.util
import json
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

import pytest

import gns3core as core
import gns3_mcp_server as server

CLI_PATH = Path(__file__).resolve().parents[1] / "cli" / "gns3lab"
LOADER = SourceFileLoader("gns3lab_pfconsoletests", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)

PID = "11111111-aaaa-bbbb-cccc-000000000001"
COMANDO = "gns3lab node props PF1 --set console_type=telnet -p lab-prueba"


def _project():
    return {"project_id": PID, "name": "lab-prueba", "status": "opened"}


def _pf(console_type="vnc", name="PF1"):
    return {
        "node_id": f"nodo-{name.lower()}",
        "name": name,
        "node_type": "qemu",
        "status": "started",
        "console": 5900,
        "console_type": console_type,
        "properties": {"adapter_type": "e1000", "hda_disk_image": "pfSense.qcow2"},
    }


def _qemu(console_type="vnc"):
    return {
        "node_id": "nodo-qemu",
        "name": "PC-QEMU",
        "node_type": "qemu",
        "status": "started",
        "console": 5901,
        "console_type": console_type,
        "properties": {"adapter_type": "e1000"},
    }


def _nat():
    return {"node_id": "nodo-nat", "name": "NAT1", "node_type": "nat", "status": "started"}


def _setup_api(fake_api, nodes):
    fake_api.set_projects([_project()])
    fake_api.set_nodes(PID, nodes)


def _cli_conf(monkeypatch, tmp_path, fake_api):
    conf = {
        "servers": {"prueba": {"url": fake_api.url, "auth": None}},
        "default_server": "prueba",
    }
    conf_path = tmp_path / "gns3lab.json"
    conf_path.write_text("{}")
    monkeypatch.setattr(cli, "CONF", conf_path)
    monkeypatch.setattr(cli, "load_conf", lambda: conf)
    return conf


@pytest.mark.parametrize("console_type", ["vnc", "spice"])
def test_verify_pf_avisa_sin_convertir_el_aviso_en_fallo(fake_api, monkeypatch, console_type):
    _setup_api(fake_api, [_pf(console_type)])
    monkeypatch.setattr(core, "_verify_pf_checks", lambda _node: [])

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "pf")

    assert resultado["ok"] is True
    assert resultado["problems"] == []
    assert len(resultado["warnings"]) == 1
    aviso = resultado["warnings"][0]
    assert console_type in aviso
    assert COMANDO in aviso
    assert "con el nodo parado" in aviso
    assert all(req["method"] == "GET" for req in fake_api.requests)


@pytest.mark.parametrize(
    ("node", "component"),
    [(_pf("telnet"), "pf"), (_qemu("vnc"), "qemu"), (_qemu("spice"), "qemu")],
)
def test_verify_no_avisa_si_telnet_o_qemu_no_pfsense(fake_api, monkeypatch, node, component):
    _setup_api(fake_api, [node])
    monkeypatch.setattr(core, "_verify_pf_checks", lambda _node: [])
    monkeypatch.setattr(core, "_verify_qemu_checks", lambda _node: [])

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", component)

    assert resultado["warnings"] == []


def test_cli_verify_texto_imprime_aviso_y_comando(fake_api, monkeypatch, capsys, tmp_path):
    _setup_api(fake_api, [_pf("vnc")])
    monkeypatch.setattr(core, "_verify_pf_checks", lambda _node: [])
    _cli_conf(monkeypatch, tmp_path, fake_api)
    monkeypatch.setattr(sys, "argv", ["gns3lab", "verify", "pf", "lab-prueba"])

    rc = cli.main()

    salida = capsys.readouterr().out
    assert rc == 0
    assert "AVISO" in salida
    assert COMANDO in salida
    assert "con el nodo parado" in salida


def test_cli_verify_json_conserva_warnings(fake_api, monkeypatch, capsys, tmp_path):
    _setup_api(fake_api, [_pf("spice")])
    monkeypatch.setattr(core, "_verify_pf_checks", lambda _node: [])
    _cli_conf(monkeypatch, tmp_path, fake_api)
    monkeypatch.setattr(sys, "argv", ["gns3lab", "verify", "pf", "lab-prueba", "--json"])

    rc = cli.main()

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["ok"] is True
    assert len(payload["warnings"]) == 1
    assert COMANDO in payload["warnings"][0]


def test_mcp_verify_devuelve_el_mismo_aviso(fake_api, monkeypatch):
    _setup_api(fake_api, [_pf("vnc")])
    monkeypatch.setattr(core, "_verify_pf_checks", lambda _node: [])
    monkeypatch.setattr(server, "_conf", lambda: {"url": fake_api.url, "user": "u", "password": "p"})

    resultado = server.gns3_verify(component="pf", project="lab-prueba")

    assert resultado["ok"] is True
    assert COMANDO in resultado["warnings"][0]
    assert "con el nodo parado" in resultado["warnings"][0]


class ServidorDoctorFalso:
    name = "prueba"
    url = "http://127.0.0.1:1"

    def __init__(self, nodes):
        self._nodes = nodes

    def alive(self):
        return True

    def get(self, path):
        if path == "/v2/version":
            return 200, {"version": "2.2.61"}
        if path == "/v2/computes":
            return 200, [{"name": "local", "connected": True}]
        raise AssertionError(path)

    def projects(self):
        return [_project()]

    def resolve(self, _needle):
        return _project()

    def nodes(self, _pid):
        return self._nodes

    def qemu_images(self):
        return ["pfSense.qcow2"]


def _prepara_doctor(monkeypatch, nodes):
    monkeypatch.setattr(cli, "Server", lambda *_a, **_k: ServidorDoctorFalso(nodes))
    monkeypatch.setattr(cli.shutil, "which", lambda _tool: "/usr/bin/herramienta")
    monkeypatch.setattr(cli.subprocess, "run", lambda *_a, **_k: SimpleNamespace(stdout="active\n"))
    monkeypatch.setattr(core, "find_monitor_port", lambda *_a, **_k: 5000)
    monkeypatch.setitem(sys.modules, "PIL", SimpleNamespace())


def test_doctor_avisa_pero_no_falla_si_pfsense_usa_vnc(monkeypatch, capsys):
    _prepara_doctor(monkeypatch, [_pf("vnc"), _nat()])
    args = SimpleNamespace(server="prueba", project="lab-prueba", json=True, check_updates=False)

    rc = cli.cmd_doctor(args, {})

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["ok"] is True
    assert payload["problems"] == []
    assert len(payload["warnings"]) == 1
    assert COMANDO in payload["warnings"][0]
    assert "con el nodo parado" in payload["warnings"][0]


def test_doctor_texto_imprime_aviso_y_comando(monkeypatch, capsys):
    _prepara_doctor(monkeypatch, [_pf("vnc"), _nat()])
    args = SimpleNamespace(server="prueba", project="lab-prueba", json=False, check_updates=False)

    rc = cli.cmd_doctor(args, {})

    salida = capsys.readouterr().out
    assert rc == 0
    assert "AVISO" in salida
    assert COMANDO in salida
    assert "con el nodo parado" in salida


@pytest.mark.parametrize("nodes", [[_pf("telnet"), _nat()], [_qemu("vnc"), _nat()]])
def test_doctor_no_avisa_si_telnet_o_qemu_no_pfsense(monkeypatch, capsys, nodes):
    _prepara_doctor(monkeypatch, nodes)
    args = SimpleNamespace(server="prueba", project="lab-prueba", json=True, check_updates=False)

    rc = cli.cmd_doctor(args, {})

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["warnings"] == []


def test_informe_mcp_incluye_aviso_de_consola(monkeypatch):
    monkeypatch.setattr(server.shutil, "which", lambda _tool: "/usr/bin/herramienta")
    monkeypatch.setattr(server.subprocess, "run", lambda *_a, **_k: SimpleNamespace(stdout="active\n"))
    monkeypatch.setattr(core, "find_monitor_port", lambda *_a, **_k: 5000)
    monkeypatch.setitem(sys.modules, "PIL", SimpleNamespace())
    status = {"running": True, "version": "2.2.61", "computes": [{"connected": True}]}
    topology = {"nodes": [_pf("vnc"), _nat()], "links": [], "nodes_error": None, "links_error": None}

    hallazgos, _pendientes = server._informe_doctor(status, _project(), None, topology)

    assert any(COMANDO in hallazgo and "con el nodo parado" in hallazgo for hallazgo in hallazgos)


class ClienteExamenFalso:
    name = "prueba"
    url = "http://127.0.0.1:1"

    def __init__(self):
        self.posts = []
        self._nodes = []
        self.contador = 0

    def projects(self):
        return []

    def get(self, path):
        if path == "/v2/templates":
            return 200, [
                {"template_id": "tpl-pf", "template_type": "qemu", "name": "pfSense",
                 "console_type": "vnc", "adapter_type": "e1000", "symbol": "firewall.svg"},
                {"template_id": "tpl-nat", "template_type": "nat", "name": "NAT"},
                {"template_id": "tpl-sw", "template_type": "ethernet_switch", "name": "SW1"},
                {"template_id": "tpl-pc", "template_type": "vpcs", "name": "VPCS"},
            ]
        if path == "/v2/computes/local/qemu/images":
            return 200, self.qemu_images()
        if "/nodes/" in path:
            nid = path.split("/nodes/", 1)[1]
            return 200, next(n for n in self._nodes if n["node_id"] == nid)
        return 404, {"message": f"sin ruta: {path}"}

    def json_list_or_die(self, path, what, **kwargs):
        st, body = self.get(path, **kwargs)
        if st != 200 or not isinstance(body, list):
            raise RuntimeError(f"{what}: [{st}] {body}")
        return body

    def qemu_images(self):
        return [{"filename": "pfSense.qcow2"}]

    def qemu_binaries(self):
        return 200, [{"path": "/usr/bin/qemu-system-x86_64"}]

    def post(self, path, body=None, **_kwargs):
        self.posts.append((path, body))
        if path == "/v2/projects":
            return 201, {"project_id": PID, "name": body["name"], "status": "opened"}
        if path.endswith("/nodes"):
            self.contador += 1
            node = {**body, "node_id": f"nodo-{self.contador}", "status": "started"}
            self._nodes.append(node)
            return 201, node
        if "/templates/" in path:
            self.contador += 1
            node = {"node_id": f"nodo-{self.contador}", "name": "NODO", "status": "started"}
            self._nodes.append(node)
            return 201, node
        return 200, {}

    def put(self, path, body=None, **_kwargs):
        nid = path.split("/nodes/", 1)[1]
        node = next(n for n in self._nodes if n["node_id"] == nid)
        node.update(body or {})
        return 200, node

    def req(self, method, path, **_kwargs):
        self.posts.append((path, {"method": method}))
        return 204, None

    def ensure_open(self, _pid):
        return None

    def drawing_create(self, _pid, body):
        self.posts.append(("drawing", body))
        return 200, {"drawing_id": "d1"}

    def project_file_write(self, _pid, path, content):
        self.posts.append((path, content))
        return 200, {}

    def nodes_action(self, _pid, action):
        self.posts.append((action, {}))
        return 200, {}

    def nodes(self, _pid):
        return self._nodes


@pytest.mark.parametrize(("console_type", "esperado"), [(None, "telnet"), ("vnc", "vnc"), ("spice", "spice")])
def test_examen_setup_fija_console_type_de_pfsense(console_type, esperado):
    cliente = ClienteExamenFalso()
    args = SimpleNamespace(from_project=None)
    if console_type is not None:
        args.console_type = console_type

    rc = cli._examen_setup(args, {}, cliente, "Kit de examen")

    assert rc == 0
    cuerpo = next(body for path, body in cliente.posts if path == f"/v2/projects/{PID}/nodes")
    assert cuerpo["console_type"] == esperado
    assert "console_type" not in cuerpo["properties"]


def test_examen_setup_rechaza_console_type_invalido():
    cliente = ClienteExamenFalso()
    args = SimpleNamespace(from_project=None, console_type="none")

    with pytest.raises(SystemExit, match="console_type no válido"):
        cli._examen_setup(args, {}, cliente, "Kit de examen")

    assert cliente.posts == []


@pytest.mark.parametrize(
    ("flags", "esperado"),
    [([], "telnet"), (["--console-type", "spice"], "spice")],
)
def test_examen_parser_aplica_console_type(monkeypatch, tmp_path, flags, esperado):
    capturado = {}

    def handler(args, _conf):
        capturado.update(vars(args))
        return 0

    conf_path = tmp_path / "gns3lab.json"
    conf_path.write_text("{}")
    monkeypatch.setattr(cli, "CONF", conf_path)
    monkeypatch.setattr(cli, "load_conf", lambda: {"default_server": "prueba"})
    monkeypatch.setattr(cli, "cmd_examen", handler)
    monkeypatch.setattr(sys, "argv", ["gns3lab", "examen", "setup", *flags])

    assert cli.main() == 0
    assert capturado["console_type"] == esperado
