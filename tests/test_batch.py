"""Contrato de `gns3_batch` y `gns3_informe` sin servidor GNS3 real."""
from __future__ import annotations

import asyncio
import inspect
import re
import unicodedata

import pytest

import gns3_mcp_server as server


def test_contrato_tools_batch_e_informe_presentes():
    tools = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
    for nombre in ("gns3_batch", "gns3_informe"):
        assert callable(getattr(server, nombre, None)), f"falta la tool {nombre}"
        assert nombre in tools


def _call(fn, *args, **kwargs):
    """Llama a la tool registrada aunque la implementación sea asíncrona."""
    result = fn(*args, **kwargs)
    return asyncio.run(result) if inspect.isawaitable(result) else result


def _fold(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()


@pytest.fixture
def batch_api(monkeypatch, fake_api):
    """API falso con credenciales y rutas ajenas que el informe debe ocultar."""
    conf = {
        "url": fake_api.url,
        "user": "usuario-contrato",
        "password": "clave-contrato",
        "host": "127.0.0.1",
        "port": "3080",
        "images_path": "/home/otro-usuario/GNS3/images",
        "projects_path": "/home/otro-usuario/GNS3/projects",
        "appliances_path": "/home/otro-usuario/GNS3/appliances",
        "configs_path": "/home/otro-usuario/GNS3/configs",
        "ubridge_path": "/home/otro-usuario/GNS3/ubridge",
    }
    monkeypatch.setattr(server, "_conf", lambda: conf)

    project = {
        "project_id": "11111111-aaaa-bbbb-cccc-000000000001",
        "name": "lab-prueba",
        "status": "opened",
        "path": "/home/otro-usuario/GNS3/projects/lab-prueba",
    }
    node = {
        "node_id": "nodo-pc1",
        "name": "PC1",
        "node_type": "vpcs",
        "status": "started",
        "console": 5001,
        "ports": [{"name": "Ethernet0", "adapter_number": 0, "port_number": 0}],
    }
    switch = {
        "node_id": "nodo-sw1",
        "name": "SW1",
        "node_type": "ethernet_switch",
        "status": "started",
        "console": 5002,
        "ports": [
            {"name": "Ethernet0", "adapter_number": 0, "port_number": 0},
            {"name": "Ethernet1", "adapter_number": 0, "port_number": 1},
        ],
    }
    link = {
        "link_id": "link-1",
        "nodes": [
            {"node_id": "nodo-pc1", "adapter_number": 0, "port_number": 0},
            {"node_id": "nodo-sw1", "adapter_number": 0, "port_number": 0},
        ],
    }
    fake_api.route("GET", "/v1/version", 200, {"version": "2.2.61"})
    fake_api.route("GET", "/v2/computes", 200, [
        {"compute_id": "local", "name": "local", "connected": True},
    ])
    fake_api.set_projects([project])
    fake_api.route("GET", f"/v2/projects/{project['project_id']}", 200, project)
    fake_api.set_nodes(project["project_id"], [node, switch])
    fake_api.route("GET", f"/v2/projects/{project['project_id']}/links", 200, [link])
    fake_api.route("GET", f"/v2/projects/{project['project_id']}/nodes/nodo-pc1", 200, {
        **node,
        "status": "stopped",
    })
    return fake_api


def test_batch_dos_lecturas_indexa_resultados_y_tiempos(batch_api):
    result = _call(server.gns3_batch, [
        {"tool": "gns3_status", "args": {}},
        {"tool": "gns3_topology", "args": {"project_name": "lab-prueba"}},
    ])

    assert result["ok"] is True
    assert type(result["total_ms"]) is int
    assert result["total_ms"] >= 0
    assert [item["index"] for item in result["results"]] == [0, 1]
    assert [item["tool"] for item in result["results"]] == ["gns3_status", "gns3_topology"]
    assert all(item["ok"] is True for item in result["results"])
    assert all(type(item["ms"]) is int and item["ms"] >= 0 for item in result["results"])
    assert result["results"][0]["result"]["version"] == "2.2.61"
    assert result["results"][1]["result"]["project"] == "lab-prueba"
    assert result["results"][1]["result"]["nodes_total"] == 2
    assert result["results"][1]["result"]["links"] == ["PC1:0/0 <-> SW1:0/0"]


def test_batch_error_no_detiene_las_demas_operaciones(batch_api):
    result = _call(server.gns3_batch, [
        {"tool": "gns3_topology", "args": {"project_name": "no-existe"}},
        {"tool": "gns3_status", "args": {}},
    ])

    assert result["ok"] is False
    assert len(result["results"]) == 2
    first, second = result["results"]
    assert first["index"] == 0
    assert first["ok"] is False
    assert "error" in first
    assert "proyecto no encontrado" in _fold(str(first["error"]))
    assert second["index"] == 1
    assert second["ok"] is True
    assert second["result"]["running"] is True
    assert batch_api.last("GET", "/v2/version")["path"] == "/v2/version"


def test_batch_stop_on_error_detiene_la_ejecucion(batch_api):
    result = _call(server.gns3_batch, [
        {"tool": "gns3_topology", "args": {"project_name": "no-existe"}},
        {"tool": "gns3_status", "args": {}},
    ], stop_on_error=True)

    assert result["ok"] is False
    assert len(result["results"]) == 1
    assert result["results"][0]["ok"] is False
    assert all(req["path"] != "/v2/version" for req in batch_api.requests)


def test_batch_rechaza_mas_de_20_operaciones_sin_ejecutarlas(batch_api):
    operations = [
        {"tool": "gns3_projects", "args": {"action": "list"}}
        for _ in range(21)
    ]

    result = _call(server.gns3_batch, operations)

    assert "error" in result
    message = _fold(str(result["error"]))
    assert "20" in message
    assert any(word in message for word in ("maximo", "limite"))
    assert batch_api.requests == []


def test_batch_bloquea_tool_destructiva_sin_confirm(batch_api):
    result = _call(server.gns3_batch, [
        {
            "tool": "gns3_node_action",
            "args": {
                "action": "stop",
                "node": "PC1",
                "project_name": "lab-prueba",
            },
        },
    ])

    assert result["ok"] is False
    item = result["results"][0]
    assert item["ok"] is False
    assert "confirm" in _fold(str(item.get("error", "")))
    assert batch_api.requests == []


def test_batch_bloquea_todas_las_mutaciones_equivalentes_sin_confirm(batch_api):
    """Hallazgo 1: la lista parcial dejaba pasar mutaciones equivalentes sin confirm."""
    operaciones = [
        {"tool": "gns3_nodes", "args": {"action": "delete", "node": "PC1", "project_name": "lab-prueba"}},
        {"tool": "gns3_nodes", "args": {"action": "stop", "node": "PC1", "project_name": "lab-prueba"}},
        {"tool": "gns3_nodes", "args": {"action": "reload", "node": "PC1", "project_name": "lab-prueba"}},
        {"tool": "gns3_node_edit", "args": {"action": "disk-resize", "node": "PC1", "size": 2048,
                                            "project_name": "lab-prueba"}},
        {"tool": "gns3_node_edit", "args": {"action": "delete", "node": "PC1", "project_name": "lab-prueba"}},
        {"tool": "gns3_console_control", "args": {"action": "reset", "node": "PC1", "project_name": "lab-prueba"}},
        {"tool": "gns3_console_control", "args": {"action": "reset-all", "project_name": "lab-prueba"}},
        {"tool": "gns3_monitor", "args": {"action": "reset", "node": "PC1", "project_name": "lab-prueba"}},
        {"tool": "gns3_snapshots", "args": {"action": "restore", "snapshot_id": "s1", "project_name": "lab-prueba"}},
        {"tool": "gns3_snapshots", "args": {"action": "delete", "snapshot_id": "s1", "project_name": "lab-prueba"}},
        {"tool": "gns3_drawings", "args": {"action": "clear", "project_name": "lab-prueba"}},
        {"tool": "gns3_drawings", "args": {"action": "delete", "drawing_id": "d1", "project_name": "lab-prueba"}},
        {"tool": "gns3_links", "args": {"action": "delete", "link_id": "link-1", "project_name": "lab-prueba"}},
        {"tool": "gns3_nio", "args": {"action": "delete", "node": "PC1", "adapter": 0, "port": 0,
                                      "project_name": "lab-prueba"}},
        {"tool": "gns3_project_io", "args": {"action": "load", "path": "/tmp/x.gns3p"}},
        {"tool": "gns3_project_io", "args": {"action": "duplicate", "project_name": "lab-prueba"}},
        {"tool": "gns3_template", "args": {"action": "delete", "name": "tpl"}},
        {"tool": "gns3_compute", "args": {"action": "delete", "cid": "local"}},
        {"tool": "gns3_gns3vm", "args": {"action": "set", "body": {}}},
        {"tool": "gns3_emulator", "args": {"action": "img-config", "body": {}}},
        {"tool": "gns3_symbols", "args": {"action": "upload", "symbol_id": "s", "content": "x"}},
        {"tool": "gns3_iou_license", "args": {"action": "set", "body": {}}},
    ]
    for op in operaciones:
        result = _call(server.gns3_batch, [op])
        item = result["results"][0]
        assert item["ok"] is False, op
        assert "confirm" in _fold(str(item.get("error", ""))), op
    assert batch_api.requests == []


def test_batch_ejecuta_tool_destructiva_confirmada_sobre_el_doble(
    batch_api, monkeypatch
):
    monkeypatch.setattr(server.time, "sleep", lambda _seconds: None)
    project_id = "11111111-aaaa-bbbb-cccc-000000000001"
    batch_api.route(
        "POST", f"/v2/projects/{project_id}/nodes/nodo-pc1/stop", 200, {"status": "stopped"}
    )

    result = _call(server.gns3_batch, [
        {
            "tool": "gns3_node_action",
            "args": {
                "action": "stop",
                "node": "PC1",
                "project_name": "lab-prueba",
            },
            "confirm": True,
        },
    ])

    assert result["ok"] is True
    assert result["results"][0]["ok"] is True
    assert result["results"][0]["result"]["status"] == "stopped"
    batch_api.last("POST", f"/v2/projects/{project_id}/nodes/nodo-pc1/stop")


def test_informe_devuelve_path_bytes_y_contenido_sin_exponer_datos(
    batch_api, tmp_path
):
    dest = tmp_path / "informe.md"

    result = _call(server.gns3_informe, project_name="lab-prueba", dest=str(dest))

    assert set(result) >= {"path", "bytes", "content"}
    assert result["path"] == str(dest)
    assert type(result["bytes"]) is int
    assert result["bytes"] == dest.stat().st_size
    assert result["content"] == dest.read_text()
    folded = _fold(result["content"])
    for value in (
        "2.2.61", "local", "lab-prueba", "PC1", "SW1",
        "pendiente de verificar",
    ):
        assert _fold(value) in folded
    for secret in ("usuario-contrato", "clave-contrato", "/home/otro-usuario"):
        assert secret not in result["content"]
    assert not re.search(
        r"(?i)(?:/home/|/users/|/root/|[a-z]:[\\/]users[\\/])", result["content"]
    )
    assert not re.search(r"https?://[^/\s:@]+:[^/@\s]+@", result["content"])
    assert not re.search(r"\bbasic\s+[a-z0-9+/=]{8,}", folded)


def test_redact_informe_ordena_secretos_mas_largos_primero_sin_residuos(monkeypatch):
    """Hallazgo 2: `_redact_informe` redactaba usuario antes que contraseña."""
    monkeypatch.setattr(server, "_conf", lambda: {"user": "admin", "password": "admin12345"})
    texto = "password admin12345 y usuario admin"

    resultado = server._redact_informe(texto)

    assert "admin12345" not in resultado
    assert "12345" not in resultado
    assert "admin" not in resultado.replace("[redactado]", "")


def test_informe_refleja_como_error_literal_un_dato_ilegible(batch_api, tmp_path):
    batch_api.route("GET", "/v2/version", 500, {"message": "fallo literal de version"})
    dest = tmp_path / "informe-error.md"

    result = _call(server.gns3_informe, project_name="lab-prueba", dest=str(dest))

    assert "fallo literal de version" in result["content"]
    assert result["content"] == dest.read_text()
    assert result["bytes"] == dest.stat().st_size
