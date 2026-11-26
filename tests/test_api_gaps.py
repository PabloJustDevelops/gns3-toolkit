"""Detalle de un enlace y de un dibujo: `link_get`, `drawing_get` y sus tools.

Los huecos venían de que sólo existía el listado (`links()`, `drawings()`); GNS3 2.2
expone además `GET /links/{lid}` y `GET /drawings/{did}`.
"""
from __future__ import annotations

import asyncio

import pytest

import gns3_mcp_server as server
from gns3core import Client

PID = "11111111-aaaa-bbbb-cccc-000000000001"
LID = "22222222-aaaa-bbbb-cccc-000000000002"
DID = "33333333-aaaa-bbbb-cccc-000000000003"


def _link() -> dict:
    return {
        "link_id": LID,
        "nodes": [{"node_id": "n1", "adapter_number": 0, "port_number": 0},
                  {"node_id": "n2", "adapter_number": 0, "port_number": 1}],
        "filters": {"latency": 50},
        "capturing": False,
        "capture_file_name": None,
    }


def _drawing() -> dict:
    return {"drawing_id": DID, "x": 10, "y": 20, "z": 0, "rotation": 0,
            "svg": '<svg width="220" height="60"></svg>'}


@pytest.fixture
def api(fake_api, monkeypatch):
    """Doble HTTP en el que las tools resuelven el proyecto y llegan al detalle."""
    conf = {"url": fake_api.url, "user": "u", "password": "p"}
    monkeypatch.setattr(server, "_conf", lambda: conf)
    project = {"project_id": PID, "name": "lab-prueba", "status": "opened"}
    fake_api.set_projects([project])
    fake_api.route("GET", f"/v2/projects/{PID}", 200, project)
    return fake_api


# ──────────────────────────────── núcleo ────────────────────────────────
def test_link_get_200(api):
    api.route("GET", f"/v2/projects/{PID}/links/{LID}", 200, _link())
    assert Client(api.url).link_get(PID, LID) == (200, _link())
    api.last("GET", f"/v2/projects/{PID}/links/{LID}")   # pid y lid van en la ruta


def test_drawing_get_200(api):
    api.route("GET", f"/v2/projects/{PID}/drawings/{DID}", 200, _drawing())
    assert Client(api.url).drawing_get(PID, DID) == (200, _drawing())
    api.last("GET", f"/v2/projects/{PID}/drawings/{DID}")


@pytest.mark.parametrize(("method", "recurso", "oid"), [
    ("link_get", "links", LID),
    ("drawing_get", "drawings", DID),
])
def test_detalle_404_conserva_estado_y_mensaje(api, method, recurso, oid):
    api.route("GET", f"/v2/projects/{PID}/{recurso}/{oid}", 404,
              {"message": f"{recurso[:-1]} no encontrado"})
    assert getattr(Client(api.url), method)(PID, oid) == (
        404, {"message": f"{recurso[:-1]} no encontrado"})


@pytest.mark.parametrize(("method", "recurso"), [
    ("link_get", "links"),
    ("drawing_get", "drawings"),
])
def test_detalle_sin_servidor_levanta_ConnectionError(method, recurso):
    with pytest.raises(ConnectionError, match="no puedo conectar"):
        getattr(Client("http://127.0.0.1:1"), method)(PID, "x")


# ───────────────────────────────── MCP ─────────────────────────────────
def test_tools_de_detalle_expuestas_con_id_obligatorio():
    tools = {t.name: t for t in asyncio.run(server.mcp.list_tools())}
    assert {"gns3_link_get", "gns3_drawing_get"} <= tools.keys()
    assert tools["gns3_link_get"].parameters["required"] == ["link_id"]
    assert tools["gns3_drawing_get"].parameters["required"] == ["drawing_id"]


def test_mcp_link_get_devuelve_el_detalle(api):
    api.route("GET", f"/v2/projects/{PID}/links/{LID}", 200, _link())
    assert server.gns3_link_get(link_id=LID, project_id=PID) == _link()


def test_mcp_drawing_get_devuelve_el_detalle(api):
    api.route("GET", f"/v2/projects/{PID}/drawings/{DID}", 200, _drawing())
    assert server.gns3_drawing_get(drawing_id=DID, project_id=PID) == _drawing()


@pytest.mark.parametrize(("tool", "recurso", "oid", "campo"), [
    (server.gns3_link_get, "links", LID, "link_id"),
    (server.gns3_drawing_get, "drawings", DID, "drawing_id"),
])
def test_mcp_detalle_404_explica_el_fallo(api, tool, recurso, oid, campo):
    api.route("GET", f"/v2/projects/{PID}/{recurso}/{oid}", 404,
              {"message": "no existe"})
    res = tool(**{campo: oid}, project_id=PID)
    assert "404" in res["error"] and res["hint"]
