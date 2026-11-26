"""Un HTTP 500 al leer plantillas no debe parecerse a «no hay plantillas»."""
from __future__ import annotations

import inspect
import json

import pytest

import gns3_mcp_server as server

PID = "11111111-aaaa-bbbb-cccc-000000000001"


@pytest.fixture
def api_500(fake_api, monkeypatch):
    conf = {"url": fake_api.url, "user": "u", "password": "p", "host": "127.0.0.1",
            "port": "3080"}
    monkeypatch.setattr(server, "_conf", lambda: conf)
    project = {"project_id": PID, "name": "lab-prueba", "status": "opened"}
    fake_api.set_projects([project])
    fake_api.route("GET", f"/v2/projects/{PID}", 200, project)
    fake_api.route("GET", "/v2/templates", 500, {"detail": "boom"})
    return fake_api


def _texto(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def test_mcp_templates_usa_json_or_die_y_devuelve_la_lista():
    class Cliente:
        def json_or_die(self, path, what):
            assert path == "/v2/templates"
            assert what == "plantillas"
            return [{"template_id": "tpl-1", "name": "VPCS"}]

    assert server._mcp_templates(Cliente()) == [
        {"template_id": "tpl-1", "name": "VPCS"}]


def test_mcp_templates_rechaza_una_respuesta_no_lista():
    class Cliente:
        def json_or_die(self, _path, _what):
            return {"detail": "boom"}

    with pytest.raises(RuntimeError, match="respuesta no válida"):
        server._mcp_templates(Cliente())


def test_resolve_template_propaga_http_500(api_500):
    with pytest.raises(RuntimeError, match=r"plantillas: \[500\]") as excinfo:
        server._resolve_template(server._client(), template_id="tpl-1")

    texto = str(excinfo.value)
    assert "boom" in texto
    assert "el servidor no tiene plantillas" not in texto
    assert "plantilla no encontrada" not in texto


def test_node_edit_create_propaga_http_500(api_500):
    with pytest.raises(RuntimeError, match=r"plantillas: \[500\]") as excinfo:
        server.gns3_node_edit(action="create", project_name="lab-prueba",
                              template="tpl-1")

    texto = str(excinfo.value)
    assert "boom" in texto
    assert "plantilla no encontrada" not in texto


def test_nodes_add_devuelve_http_500_en_lugar_de_lista_vacia(api_500):
    resultado = server.gns3_nodes(project_name="lab-prueba", action="add",
                                  template="tpl-1")

    assert isinstance(resultado, dict)
    assert "[500]" in resultado["error"]
    assert "boom" in _texto(resultado)
    assert "plantilla no encontrada" not in _texto(resultado)
    assert "available" not in resultado


def test_los_tres_call_sites_no_usan_lecturas_directas_inseguras():
    resolve = inspect.getsource(server._resolve_template)
    node_edit = inspect.getsource(server.gns3_node_edit)
    nodes = inspect.getsource(server.gns3_nodes)

    assert "_mcp_templates(client)" in resolve
    assert "_mcp_templates(client)" in node_edit
    assert "client.templates()" not in resolve
    assert "client.templates()" not in node_edit
    assert '_api("GET", "/v2/templates") or []' not in nodes
