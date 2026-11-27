"""Contrato de `gns3lab examen` con Namespace y API GNS3 falsos."""
from __future__ import annotations

import importlib.util
import json
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

import pytest

CLI_PATH = Path(__file__).resolve().parents[1] / "cli" / "gns3lab"
LOADER = SourceFileLoader("gns3lab_extests", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)


def test_contrato_handler_examen_presente():
    assert callable(getattr(cli, "cmd_examen", None))


@pytest.fixture
def exam_conf(fake_api):
    """Configuración aislada: el único servidor posible es el API falso."""
    project = {
        "project_id": "11111111-aaaa-bbbb-cccc-000000000001",
        "name": "Kit de examen",
        "status": "opened",
    }
    fake_api.set_projects([project])
    fake_api.route("GET", f"/v2/projects/{project['project_id']}", 200, project)
    fake_api.set_nodes(project["project_id"], [])
    fake_api.route("GET", f"/v2/projects/{project['project_id']}/links", 200, [])
    fake_api.route("GET", "/v2/templates", 200, [])
    fake_api.route("GET", "/v2/computes", 200, [])
    fake_api.route("GET", "/v2/computes/local", 200, {"compute_id": "local"})
    fake_api.route("GET", "/v2/computes/local/qemu/images", 200, [])
    return {
        "servers": {
            "prueba": {"url": fake_api.url, "auth": None},
        },
        "default_server": "prueba",
    }


def _args(action: str, **overrides) -> SimpleNamespace:
    values = {
        "action": action,
        "server": "prueba",
        "name": "Kit de examen",
        "from_project": None,
        "json": False,
        "yes": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_examen_verify_json_devuelve_ok_y_problems(exam_conf, fake_api, capsys):
    try:
        cli.cmd_examen(_args("verify", json=True), exam_conf)
    except SystemExit as exc:
        assert exc.code not in (None, 0)

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert isinstance(payload["ok"], bool)
    assert isinstance(payload["problems"], list)
    assert payload["ok"] is False
    assert payload["problems"]


def test_examen_reset_sin_yes_se_rechaza_antes_de_tocar_servidor(
    exam_conf, fake_api, capsys
):
    try:
        result = cli.cmd_examen(_args("reset"), exam_conf)
    except SystemExit as exc:
        result = exc.code

    assert result not in (None, 0)
    captured = capsys.readouterr()
    assert "--yes" in captured.out + captured.err
    assert fake_api.requests == []


# ─────────────────────── hallazgos swarm `fix-cli-examen` ───────────────────────

def test_asegurar_wan_no_necesita_uuid_global():
    """`_asegurar_wan` usa `uuid`; no puede depender de imports locales de otros comandos."""
    topo = {
        "topology": {
            "nodes": [{
                "node_id": "fw-1", "node_type": "qemu", "name": "PF1",
                "properties": {"adapters": 2},
            }],
            "links": [],
        }
    }
    cambios: list[str] = []
    cli._asegurar_wan(None, topo, cambios)
    assert any(n["node_type"] == "nat" for n in topo["topology"]["nodes"])
    assert len(topo["topology"]["links"]) == 1
    assert topo["topology"]["links"][0]["nodes"][0]["node_id"] == "fw-1"
    assert cambios


# kit completo contra dobles en memoria (sin servidor GNS3)
_PID = "22222222-aaaa-bbbb-cccc-000000000002"
_KIT_TEMPLATES = [
    {"template_id": "tpl-pf", "template_type": "qemu", "name": "pfSense",
     "qemu_path": "/usr/bin/qemu-system-x86_64"},
    {"template_id": "tpl-nat", "template_type": "nat", "name": "NAT"},
    {"template_id": "tpl-sw", "template_type": "ethernet_switch", "name": "Switch"},
    {"template_id": "tpl-vpcs", "template_type": "vpcs", "name": "VPCS"},
]
_KIT_NODES = [
    {"node_id": "n-pf", "name": "PF1", "node_type": "qemu", "status": "started"},
    {"node_id": "n-nat", "name": "NAT1", "node_type": "nat", "status": "started"},
    {"node_id": "n-sw", "name": "SW1", "node_type": "ethernet_switch", "status": "started"},
    {"node_id": "n-pc1", "name": "PC1", "node_type": "vpcs", "status": "started"},
    {"node_id": "n-pc2", "name": "PC2", "node_type": "vpcs", "status": "started"},
]
_NODE_POR_TEMPLATE = {
    "tpl-nat": "n-nat", "tpl-sw": "n-sw", "tpl-vpcs": "n-pc1",
}


class _SetupFakeC:
    """Doble de `core.Client` para `_examen_setup`."""

    name = "prueba"
    url = "http://prueba"

    def __init__(self, *, templates=None, qemu_binaries=None, marker_status=201,
                 existing=None, images=None):
        self._templates = list(_KIT_TEMPLATES if templates is None else templates)
        self._qemu_binaries = qemu_binaries if qemu_binaries is not None else [
            {"path": "/usr/bin/qemu-system-x86_64"}]
        self._marker_status = marker_status
        self._existing = list(existing or [])
        self._images = images if images is not None else [{"filename": "pfSense-examen.qcow2"}]
        self.posts: list[tuple[str, object]] = []
        self.deletes: list[str] = []
        self._vpcs_n = 0

    def projects(self):
        return list(self._existing)

    def json_or_die(self, path, what):
        if path == "/v2/templates":
            return list(self._templates)
        raise AssertionError(f"json_or_die inesperado: {path}")

    def json_list_or_die(self, path, what):
        return list(self._images)

    def qemu_binaries(self):
        return 200, list(self._qemu_binaries)

    def post(self, path, payload=None, **kw):
        self.posts.append((path, payload))
        if path == "/v2/projects":
            return 201, {"project_id": _PID, "name": (payload or {}).get("name")}
        if path == f"/v2/projects/{_PID}/nodes":
            return 201, {"node_id": "n-pf"}
        if path.endswith("/links"):
            return 201, {}
        if path.endswith("/nodes/start"):
            return 200, {}
        if "/templates/" in path:
            tpl = path.rsplit("/", 1)[1]
            if tpl == "tpl-vpcs":
                self._vpcs_n += 1
                return 201, {"node_id": f"n-pc{self._vpcs_n}"}
            return 201, {"node_id": _NODE_POR_TEMPLATE.get(tpl, "n-x")}
        return 200, {}

    def put(self, path, payload, **kw):
        return 200, {}

    def ensure_open(self, pid):
        return None

    def req(self, method, path, data=None, ctype=None, timeout=None):
        return 201, {}

    def drawing_create(self, pid, body):
        return 201, {}

    def project_file_write(self, pid, path, content):
        return self._marker_status, {}

    def nodes_action(self, pid, action, timeout=300):
        self.posts.append((f"/v2/projects/{pid}/nodes/{action}", None))
        return 200, {}

    def nodes(self, pid):
        return [dict(n) for n in _KIT_NODES]

    def delete(self, path, **kw):
        self.deletes.append(path)
        return 204, {}


def _setup_args():
    return _args("setup", json=False)


def test_examen_setup_no_dice_listo_si_fallan_arranques(monkeypatch, capsys):
    c = _SetupFakeC()
    monkeypatch.setattr(cli, "_wait_node_status", lambda *a, **k: "stopped")
    result = cli._examen_setup(_setup_args(), {}, c, "Kit de examen")
    out = capsys.readouterr().out
    assert result != 0
    assert "listo:" not in out


def test_examen_setup_precondicion_no_crea_proyecto(monkeypatch):
    """Sin binarios QEMU no se crea nada; el reintento no encuentra nombre ocupado."""
    # plantilla sin qemu_path propio + servidor sin binarios QEMU
    templates = [dict(t) for t in _KIT_TEMPLATES]
    templates[0].pop("qemu_path", None)
    c = _SetupFakeC(templates=templates, qemu_binaries=[])
    monkeypatch.setattr(cli, "_wait_node_status", lambda *a, **k: "started")
    with pytest.raises(SystemExit):
        cli._examen_setup(_setup_args(), {}, c, "Kit de examen")
    assert all(path != "/v2/projects" for path, _ in c.posts), c.posts


def test_examen_setup_comprueba_escritura_examen_marker(monkeypatch):
    """Si falla la escritura de la marca, `reset` no puede exigir una marca inexistente."""
    c = _SetupFakeC(marker_status=500)
    monkeypatch.setattr(cli, "_wait_node_status", lambda *a, **k: "started")
    with pytest.raises(SystemExit):
        cli._examen_setup(_setup_args(), {}, c, "Kit de examen")
    # no se llega a arrancar los nodos con una marca que no se pudo grabar
    assert not any(path.endswith("/nodes/start") for path, _ in c.posts)


def test_examen_verify_json_servidor_caido_devuelve_json(capsys):
    conf = {"servers": {"prueba": {"url": "http://127.0.0.1:1", "auth": None}},
            "default_server": "prueba"}
    result = cli.cmd_examen(_args("verify", json=True), conf)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result != 0
    assert payload["ok"] is False
    assert payload["problems"]


def test_test_vpcs_sin_consola_o_error_cuenta_como_fallo(monkeypatch, capsys):
    """Un VPCS sin consola o inalcanzable no se cuela como éxito si otro ping pasa."""
    proj = {"project_id": "p", "name": "kit"}

    class _Server:
        url = "http://prueba"

        def __init__(self, *a, **k): pass
        def resolve(self, needle): return proj
        def nodes(self, pid):
            return [
                {"name": "PC1", "node_type": "vpcs", "console": None, "console_type": "telnet"},
                {"name": "PC2", "node_type": "vpcs", "console": 5001, "console_type": "telnet"},
            ]

    class _VpcsOk:
        def __init__(self, host, port, timeout=10.0): pass
        def run(self, *cmds, settle=5.0):
            joined = " ".join(cmds)
            if joined.startswith("ping"):
                return "84 bytes from 192.168.1.1 icmp_seq=1 time=1.2 ms"
            return "IP/MASK : 192.168.1.100/24\nGATEWAY : 192.168.1.1"
        def close(self): pass

    monkeypatch.setattr(cli, "Server", _Server)
    monkeypatch.setattr(cli, "Vpcs", _VpcsOk)
    args = SimpleNamespace(server="prueba", project="kit", keep_open=False)
    result = cli.cmd_test(args, {})
    assert result != 0


def test_examen_doc_unico_nombre_proyecto():
    doc = (Path(cli.__file__).resolve().parents[1] / "docs" / "EXAMEN.md").read_text(
        encoding="utf-8")
    assert cli.EXAMEN_NAME == "Kit de examen"
    assert cli.EXAMEN_NAME in doc
    assert "examen-kit" not in doc
    assert "El proyecto se llama `examen`" not in doc


# ── hallazgo 8: `examen verify` comprueba enlaces prometidos y mapa VLAN ──

def _kit_vlan(*, links, sw_ports=None):
    sw_props = {"ports_mapping": sw_ports if sw_ports is not None else [
        {"name": "Ethernet0", "port_number": 0, "type": "access", "vlan": 1, "ethertype": ""},
        {"name": "Ethernet1", "port_number": 1, "type": "access", "vlan": 1, "ethertype": ""},
        {"name": "Ethernet2", "port_number": 2, "type": "access", "vlan": 1, "ethertype": ""},
        {"name": "Ethernet3", "port_number": 3, "type": "access", "vlan": 1, "ethertype": ""},
    ]}
    nodes = [
        {"node_id": "n-pf", "name": "PF1", "node_type": "qemu", "status": "started",
         "properties": {"linked_clone": True, "hda_disk_image": "pfSense.qcow2"}},
        {"node_id": "n-nat", "name": "NAT1", "node_type": "nat", "status": "started", "properties": {}},
        {"node_id": "n-sw", "name": "SW1", "node_type": "ethernet_switch", "status": "started",
         "properties": sw_props},
        {"node_id": "n-pc1", "name": "PC1", "node_type": "vpcs", "status": "started", "properties": {}},
        {"node_id": "n-pc2", "name": "PC2", "node_type": "vpcs", "status": "started", "properties": {}},
    ]
    return nodes, links


def _link(a, aa, ap, b, ba, bp):
    return {"link_id": f"{a}-{b}-{aa}-{ap}-{ba}-{bp}", "link_type": "ethernet",
            "nodes": [{"node_id": a, "adapter_number": aa, "port_number": ap},
                      {"node_id": b, "adapter_number": ba, "port_number": bp}]}


_KIT_LINKS_OK = [
    _link("n-pf", 0, 0, "n-nat", 0, 0),
    _link("n-pf", 1, 0, "n-sw", 0, 0),
    _link("n-pc1", 0, 0, "n-sw", 0, 1),
    _link("n-pc2", 0, 0, "n-sw", 0, 2),
]


class _VerifyFakeC:
    name = "prueba"
    url = "http://prueba"

    def __init__(self, nodes, links, project_name="Kit de examen"):
        self._nodes = nodes
        self._links = links
        self._project_name = project_name

    def alive(self): return True
    def version(self): return {"version": "2.2.61"}
    def projects(self):
        return [{"project_id": "p", "name": self._project_name, "status": "opened"}]
    def ensure_open(self, pid): return None
    def nodes(self, pid): return list(self._nodes)
    def links(self, pid): return list(self._links)


def test_examen_verify_comprueba_enlaces_y_mapa_vlan(monkeypatch, capsys):
    nodes, _ = _kit_vlan(links=_KIT_LINKS_OK)
    # mapa VLAN del switch con una entrada quitada: un puerto en uso sin definición
    sw_ports = [dict(p) for p in nodes[2]["properties"]["ports_mapping"]]
    sw_ports = [p for p in sw_ports if p["port_number"] != 1]  # Ethernet1 (PC1) sin entrada
    nodes[2]["properties"]["ports_mapping"] = sw_ports
    c = _VerifyFakeC(nodes, list(_KIT_LINKS_OK))
    # no verificar ping real en este test de enlaces/VLAN
    monkeypatch.setattr(cli.core, "console_for",
                        lambda *a, **k: (_ for _ in ()).throw(cli.core.ConsoleError("sin consola")))
    args = _args("verify", json=True)
    result = cli._examen_verify(args, {}, c, "Kit de examen")
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result != 0
    # el check de ping puede fallar por el doble; lo relevante es mapa VLAN
    assert payload["checks"].get("vlan_map") is False, payload["checks"]
    assert "SW1" in "\n".join(payload["problems"])


def test_examen_verify_enlace_prometido_ausente(monkeypatch, capsys):
    nodes, _ = _kit_vlan(links=_KIT_LINKS_OK)
    links = [l for l in _KIT_LINKS_OK if l["nodes"][0]["node_id"] != "n-pc2"]
    c = _VerifyFakeC(nodes, links)
    monkeypatch.setattr(cli.core, "console_for",
                        lambda *a, **k: (_ for _ in ()).throw(cli.core.ConsoleError("sin consola")))
    result = cli._examen_verify(_args("verify", json=True), {}, c, "Kit de examen")
    payload = json.loads(capsys.readouterr().out)
    assert result != 0
    assert payload["checks"].get("links") is False, payload["checks"]
    assert "PC2" in "\n".join(payload["problems"])
