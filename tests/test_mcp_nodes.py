"""Contrato de gns3_nodes: borrar un nodo no debe releerlo como si siguiera vivo."""
from __future__ import annotations

import pytest

import gns3_mcp_server as server

PID = "11111111-aaaa-bbbb-cccc-000000000001"
NID = "nodo-pc1"


@pytest.fixture
def api(fake_api, monkeypatch):
    conf = {"url": fake_api.url, "user": "u", "password": "p", "host": "127.0.0.1",
            "port": "3080"}
    monkeypatch.setattr(server, "_conf", lambda: conf)
    monkeypatch.setattr(server.time, "sleep", lambda _seconds: None)
    project = {"project_id": PID, "name": "lab-prueba", "status": "opened"}
    node = {"node_id": NID, "name": "PC1", "node_type": "vpcs", "status": "stopped",
            "console": 5001, "ports": []}
    fake_api.set_projects([project])
    fake_api.route("GET", f"/v2/projects/{PID}", 200, project)
    fake_api.set_nodes(PID, [node])
    return fake_api


def test_delete_exitoso_no_reporta_un_404_de_la_relectura(api):
    api.route("DELETE", f"/v2/projects/{PID}/nodes/{NID}", 204, None)

    result = server.gns3_nodes(project_name="lab-prueba", action="delete", node="PC1")

    assert result == [{"name": "PC1", "request_ok": True, "status": None, "detail": None}]
    assert api.last("DELETE", f"/v2/projects/{PID}/nodes/{NID}")
