"""Velocidad y aislamiento de `gns3_batch` sin servidor GNS3."""
from __future__ import annotations

import asyncio
import inspect
import threading

import pytest

import gns3_mcp_server as server

BATCH_SOURCE = inspect.getsource(server.gns3_batch)
PARALLEL_READY = all(token in BATCH_SOURCE for token in (
    "ThreadPoolExecutor", '"parallel"', '"wall_ms"',
))
requires_parallel = pytest.mark.skipif(
    not PARALLEL_READY,
    reason="BRIEF-pfmcp pendiente: gns3_batch no expone ejecución paralela ni wall_ms",
)


def _call(fn, *args, **kwargs):
    result = fn(*args, **kwargs)
    return asyncio.run(result) if inspect.isawaitable(result) else result


@requires_parallel
def test_batch_cinco_lecturas_conserva_orden_y_reporta_paralelo(monkeypatch):
    barrier = threading.Barrier(5, timeout=1)

    def read(**kwargs):
        barrier.wait()
        return {"version": "2.2.61", "running": True}

    tools = ("gns3_status", "gns3_projects", "gns3_topology", "gns3_templates", "gns3_symbols")
    monkeypatch.setattr(server, "_registered_tool_functions", lambda: {name: read for name in tools})
    operations = [
        {"tool": "gns3_status", "args": {}},
        {"tool": "gns3_projects", "args": {"action": "list"}},
        {"tool": "gns3_topology", "args": {}},
        {"tool": "gns3_templates", "args": {}},
        {"tool": "gns3_symbols", "args": {}},
    ]

    result = _call(server.gns3_batch, operations)

    assert result["ok"] is True
    assert result["parallel"] is True
    assert type(result["wall_ms"]) is int
    assert result["wall_ms"] >= 0
    assert [item["index"] for item in result["results"]] == [0, 1, 2, 3, 4]
    assert [item["tool"] for item in result["results"]] == list(tools)
    assert all(item["ok"] is True for item in result["results"])
    assert all(item["result"]["version"] == "2.2.61" for item in result["results"])


def test_batch_una_operacion_con_error_no_rompe_las_demas(monkeypatch):
    def status():
        return {"error": "fallo literal de lectura"}

    def projects(action="list"):
        return [{"name": "lab-prueba", "status": "opened"}]

    def topology():
        return {"nodes_total": 2}

    monkeypatch.setattr(server, "_registered_tool_functions", lambda: {
        "gns3_status": status,
        "gns3_projects": projects,
        "gns3_topology": topology,
    })

    result = _call(server.gns3_batch, [
        {"tool": "gns3_status", "args": {}},
        {"tool": "gns3_projects", "args": {"action": "list"}},
        {"tool": "gns3_topology", "args": {}},
    ])

    assert result["ok"] is False
    assert [item["index"] for item in result["results"]] == [0, 1, 2]
    assert result["results"][0]["ok"] is False
    assert result["results"][0]["error"] == "fallo literal de lectura"
    assert result["results"][1]["ok"] is True
    assert result["results"][1]["result"][0]["name"] == "lab-prueba"
    assert result["results"][2]["ok"] is True
    assert result["results"][2]["result"]["nodes_total"] == 2


@requires_parallel
def test_batch_efectos_secundarios_no_se_paralelizan(monkeypatch):
    barrier = threading.Barrier(2, timeout=0.2)
    lock = threading.Lock()
    activas = 0
    maximo_activas = 0
    orden = []

    def node_action(action, node, confirm=False):
        nonlocal activas, maximo_activas
        with lock:
            activas += 1
            maximo_activas = max(maximo_activas, activas)
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            pass
        with lock:
            activas -= 1
            orden.append(node)
        return {"status": "stopped", "node": node}

    monkeypatch.setattr(server, "_registered_tool_functions", lambda: {
        "gns3_node_action": node_action,
    })

    result = _call(server.gns3_batch, [
        {"tool": "gns3_node_action", "args": {"action": "stop", "node": "PC1"}, "confirm": True},
        {"tool": "gns3_node_action", "args": {"action": "stop", "node": "PC2"}, "confirm": True},
    ])

    assert result["ok"] is True
    assert result["parallel"] is False
    assert maximo_activas == 1
    assert orden == ["PC1", "PC2"]
    assert [item["index"] for item in result["results"]] == [0, 1]
