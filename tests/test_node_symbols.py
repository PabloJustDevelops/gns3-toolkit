"""Contrato de símbolos al crear nodos: defaults, override y errores accionables."""
from __future__ import annotations

import json

import pytest

import gns3core as core
import gns3_mcp_server as server

PID = "11111111-aaaa-bbbb-cccc-000000000001"
NID = "22222222-aaaa-bbbb-cccc-000000000002"
TID = "33333333-aaaa-bbbb-cccc-000000000003"
NODES_PATH = f"/v2/projects/{PID}/nodes"
TEMPLATE_NODE_PATH = f"/v2/projects/{PID}/templates/{TID}"


def _body(request: dict) -> dict:
    return json.loads(request["body"] or b"{}")


def _node(node_type: str, symbol: str | None) -> dict:
    return {
        "node_id": NID,
        "project_id": PID,
        "name": f"{node_type}-1",
        "node_type": node_type,
        "compute_id": "local",
        "status": "stopped",
        "console": None,
        "console_type": None,
        "ports": [],
        "properties": {},
        "symbol": symbol,
    }


@pytest.fixture
def api(fake_api, monkeypatch):
    conf = {"url": fake_api.url, "user": "u", "password": "p", "host": "127.0.0.1",
            "port": "3080"}
    monkeypatch.setattr(server, "_conf", lambda: conf)
    project = {"project_id": PID, "name": "lab-prueba", "status": "opened"}
    fake_api.set_projects([project])
    fake_api.route("GET", f"/v2/projects/{PID}", 200, project)
    fake_api.route("GET", "/v2/symbols", 200, [
        {"symbol_id": ":/symbols/classic/cloud.svg", "filename": "cloud.svg"},
        {"symbol_id": ":/symbols/classic/nat.svg", "filename": "nat.svg"},
        {"symbol_id": ":/symbols/classic/firewall.svg", "filename": "firewall.svg"},
        {"symbol_id": ":/symbols/classic/computer.svg", "filename": "computer.svg"},
    ])
    return fake_api


@pytest.mark.parametrize(("node_type", "expected"), [
    ("cloud", "cloud.svg"),
    ("nat", "nat.svg"),
    ("qemu", None),
    ("vpcs", None),
])
def test_default_symbol(node_type, expected):
    assert core.default_symbol(node_type) == expected


def test_symbol_error_ignora_entradas_invalidas_y_lista_vacia():
    assert core.symbol_error([None, {"filename": "nat.svg"}], "nat.svg") is None
    problema = core.symbol_error([None], "cloud.svg")
    assert problema["available"] == []
    assert "(ninguno)" in problema["error"]


@pytest.mark.parametrize(("node_type", "expected"), [
    ("cloud", "cloud.svg"),
    ("nat", "nat.svg"),
])
def test_node_create_envia_el_simbolo_por_defecto(fake_api, node_type, expected):
    path = "/v2/projects/p1/nodes"
    fake_api.route("POST", path, 201, _node(node_type, expected))

    status, _ = core.Client(fake_api.url).node_create("p1", {
        "name": f"{node_type}-1", "node_type": node_type,
        "compute_id": "local", "properties": {},
    })

    assert status == 201
    assert _body(fake_api.last("POST", path))["symbol"] == expected


def test_node_create_qemu_sin_flag_no_inventa_simbolo(fake_api):
    path = "/v2/projects/p1/nodes"
    fake_api.route("POST", path, 201, _node("qemu", ":/symbols/classic/computer.svg"))

    core.Client(fake_api.url).node_create("p1", {
        "name": "PF2", "node_type": "qemu", "compute_id": "local",
        "properties": {"ram": 256},
    })

    assert "symbol" not in _body(fake_api.last("POST", path))


def test_node_create_respeta_un_override_explicito(fake_api):
    path = "/v2/projects/p1/nodes"
    fake_api.route("POST", path, 201, _node("cloud", "firewall.svg"))

    core.Client(fake_api.url).node_create("p1", {
        "name": "Cloud-lab", "node_type": "cloud", "compute_id": "local",
        "properties": {},
    }, symbol="firewall.svg")

    assert _body(fake_api.last("POST", path))["symbol"] == "firewall.svg"


@pytest.mark.parametrize(("node_type", "properties", "expected"), [
    ("cloud", {"ports_mapping": []}, "cloud.svg"),
    ("nat", {"ports_mapping": []}, "nat.svg"),
    ("qemu", {"ram": 256}, None),
])
def test_mcp_create_directo_aplica_defaults_y_reporta_el_simbolo(
        api, node_type, properties, expected):
    api.route("POST", NODES_PATH, 201,
              _node(node_type, expected or ":/symbols/classic/computer.svg"))

    result = server.gns3_node_edit(action="create", project_name="lab-prueba",
                                   name=f"{node_type}-1", node_type=node_type,
                                   properties=properties)

    assert "error" not in result, result
    assert result["symbol"] == (expected or ":/symbols/classic/computer.svg")
    sent = _body(api.last("POST", NODES_PATH))
    if expected is None:
        assert "symbol" not in sent
    else:
        assert sent["symbol"] == expected


def test_mcp_create_directo_con_symbol_inexistente_no_crea_nada(api):
    result = server.gns3_node_edit(action="create", project_name="lab-prueba",
                                   node_type="qemu", properties={"ram": 256},
                                   symbol="no-existe.svg")

    assert "no-existe.svg" in result["error"]
    assert ":/symbols/classic/firewall.svg" in result["available"]
    assert not any(r["method"] == "POST" and r["path"] == NODES_PATH
                   for r in api.requests)


def test_mcp_create_directo_envia_un_symbol_explicito_valido(api):
    api.route("POST", NODES_PATH, 201,
              _node("qemu", ":/symbols/classic/firewall.svg"))

    result = server.gns3_node_edit(action="create", project_name="lab-prueba",
                                   node_type="qemu", properties={"ram": 256},
                                   symbol=":/symbols/classic/firewall.svg")

    assert result["symbol"] == ":/symbols/classic/firewall.svg"
    assert _body(api.last("POST", NODES_PATH))["symbol"] == \
        ":/symbols/classic/firewall.svg"


def _rutas_plantilla(api, symbol=":/symbols/classic/nat.svg"):
    api.route("GET", "/v2/templates", 200, [{
        "template_id": TID, "name": "NAT", "template_type": "nat", "symbol": symbol,
    }])
    api.route("POST", TEMPLATE_NODE_PATH, 201, _node("nat", symbol))


def test_mcp_node_edit_create_desde_plantilla_configura_nombre_y_symbol(api):
    _rutas_plantilla(api)
    node_path = f"{NODES_PATH}/{NID}"
    actualizado = _node("nat", ":/symbols/classic/firewall.svg")
    actualizado["name"] = "NAT2"
    api.route("PUT", node_path, 200, actualizado)

    result = server.gns3_node_edit(action="create", project_name="lab-prueba",
                                   template="NAT", name="NAT2",
                                   symbol=":/symbols/classic/firewall.svg")

    assert result["name"] == "NAT2"
    assert result["symbol"] == ":/symbols/classic/firewall.svg"
    assert _body(api.last("PUT", node_path)) == {
        "name": "NAT2", "symbol": ":/symbols/classic/firewall.svg",
    }


def test_mcp_node_edit_si_falla_el_put_identifica_el_nodo_ya_creado(api):
    _rutas_plantilla(api)
    api.route("PUT", f"{NODES_PATH}/{NID}", 500, {"message": "boom"})

    result = server.gns3_node_edit(action="create", project_name="lab-prueba",
                                   template="NAT", name="NAT2",
                                   symbol=":/symbols/classic/firewall.svg")

    assert NID in result["error"]
    assert "creado" in result["error"]
    assert "no se pudo configurar" in result["error"]
    assert "boom" in result["error"]


def test_mcp_nodes_add_aplica_symbol_despues_de_instanciar_la_plantilla(api):
    _rutas_plantilla(api)
    node_path = f"{NODES_PATH}/{NID}"
    api.route("PUT", node_path, 200, _node("nat", ":/symbols/classic/firewall.svg"))

    result = server.gns3_nodes(project_name="lab-prueba", action="add",
                               template="NAT", symbol=":/symbols/classic/firewall.svg")

    assert "error" not in result, result
    assert result["symbol"] == ":/symbols/classic/firewall.svg"
    assert _body(api.last("PUT", node_path)) == {"symbol": ":/symbols/classic/firewall.svg"}


def test_mcp_nodes_add_sin_symbol_conserva_el_de_la_plantilla(api):
    _rutas_plantilla(api)

    result = server.gns3_nodes(project_name="lab-prueba", action="add", template="NAT")

    assert result["symbol"] == ":/symbols/classic/nat.svg"
    assert not any(r["method"] == "PUT" for r in api.requests)


def test_mcp_nodes_add_con_symbol_inexistente_no_instancia_la_plantilla(api):
    _rutas_plantilla(api)

    result = server.gns3_nodes(project_name="lab-prueba", action="add",
                               template="NAT", symbol="no-existe.svg")

    assert "no-existe.svg" in result["error"]
    assert ":/symbols/classic/cloud.svg" in result["available"]
    assert not any(r["method"] == "POST" and r["path"] == TEMPLATE_NODE_PATH
                   for r in api.requests)
