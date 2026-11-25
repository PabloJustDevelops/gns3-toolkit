"""Contratos de resources y prompts del MCP, sin servidor GNS3 real."""
from __future__ import annotations

import asyncio
import inspect
import json
import re
import unicodedata
from pathlib import Path

import pytest

import gns3_mcp_server as server

RESOURCE_URIS = (
    "gns3://status",
    "gns3://projects",
    "gns3://project/{project}/topology",
    "gns3://templates",
)
PROMPT_NAMES = ("gns3-diagnostico", "gns3-examen")


def _registrations():
    """Descubre las funciones registradas sin abrir transporte ni cliente MCP."""
    resources = {
        str(item.uri): item
        for item in asyncio.run(server.mcp.list_resources())
    }
    resources.update({
        item.uri_template: item
        for item in asyncio.run(server.mcp.list_resource_templates())
    })
    prompts = {
        item.name: item
        for item in asyncio.run(server.mcp.list_prompts())
    }
    return resources, prompts


REGISTERED_RESOURCES, REGISTERED_PROMPTS = _registrations()
MISSING_RESOURCES = tuple(sorted(set(RESOURCE_URIS) - REGISTERED_RESOURCES.keys()))
MISSING_PROMPTS = tuple(sorted(set(PROMPT_NAMES) - REGISTERED_PROMPTS.keys()))
requires_resources = pytest.mark.skipif(
    bool(MISSING_RESOURCES),
    reason="BRIEF-mcpres pendiente: faltan resources " + ", ".join(MISSING_RESOURCES),
)
requires_prompts = pytest.mark.skipif(
    bool(MISSING_PROMPTS),
    reason="BRIEF-mcpres pendiente: faltan prompts " + ", ".join(MISSING_PROMPTS),
)


def _call(fn, *args, **kwargs):
    """Llama directamente a la función registrada, también si es asíncrona."""
    result = fn(*args, **kwargs)
    return asyncio.run(result) if inspect.isawaitable(result) else result


def _text(value) -> str:
    """Convierte datos estructurados o texto a una representación comprobable."""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _fold(value: str) -> str:
    """Minúsculas sin acentos para no exigir una redacción concreta."""
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()


@pytest.fixture
def mcp_api(monkeypatch, fake_api):
    """Apunta el MCP al API falsa y declara los datos del contrato."""
    conf = {
        "url": fake_api.url,
        "user": "usuario-contrato",
        "password": "clave-contrato",
        "host": "127.0.0.1",
        "port": "3080",
        "images_path": "",
        "projects_path": "",
        "appliances_path": "",
        "configs_path": "",
        "ubridge_path": "",
    }
    monkeypatch.setattr(server, "_conf", lambda: conf)
    monkeypatch.setenv("GNS3_URL", fake_api.url)
    monkeypatch.setenv("GNS3_USER", conf["user"])
    monkeypatch.setenv("GNS3_PASSWORD", conf["password"])

    project = {
        "project_id": "11111111-aaaa-bbbb-cccc-000000000001",
        "name": "lab-prueba",
        "status": "opened",
    }
    other = {
        "project_id": "22222222-aaaa-bbbb-cccc-000000000002",
        "name": "examen-dic",
        "status": "closed",
    }
    fake_api.set_projects([project, other])
    fake_api.route("GET", f"/v2/projects/{project['project_id']}", 200, project)
    fake_api.route("GET", f"/v2/projects/{other['project_id']}", 200, other)
    fake_api.set_nodes(project["project_id"], [
        {
            "node_id": "nodo-pc1",
            "name": "PC1",
            "node_type": "vpcs",
            "status": "started",
            "console": 5001,
            "ports": [{"name": "Ethernet0"}],
        },
        {
            "node_id": "nodo-sw1",
            "name": "SW1",
            "node_type": "ethernet_switch",
            "status": "started",
            "console": 5002,
            "ports": [{"name": "Ethernet0"}, {"name": "Ethernet1"}],
        },
    ])
    fake_api.route("GET", f"/v2/projects/{project['project_id']}/links", 200, [
        {"link_id": "link-1", "nodes": [
            {"node_id": "nodo-pc1", "adapter_number": 0, "port_number": 0},
            {"node_id": "nodo-sw1", "adapter_number": 0, "port_number": 0},
        ]},
    ])
    fake_api.route("GET", "/v2/templates", 200, [
        {"template_id": "tpl-pfsense", "name": "pfSense", "template_type": "qemu"},
        {"template_id": "tpl-vpcs", "name": "VPCS", "template_type": "vpcs"},
    ])
    fake_api.route("GET", "/v2/computes", 200, [
        {"compute_id": "local", "name": "local", "connected": True},
    ])
    fake_api.route("GET", "/v2/computes/local", 200, {
        "compute_id": "local", "name": "local", "connected": True,
    })
    return fake_api


@requires_resources
@requires_prompts
def test_uris_y_nombres_esperados_estan_registrados():
    assert set(RESOURCE_URIS) <= REGISTERED_RESOURCES.keys()
    assert set(PROMPT_NAMES) <= REGISTERED_PROMPTS.keys()


@pytest.mark.parametrize(
    ("uri", "kwargs", "expected"),
    [
        ("gns3://status", {}, ("2.2.61",)),
        ("gns3://projects", {}, ("lab-prueba", "examen-dic")),
        (
            "gns3://project/{project}/topology",
            {"project": "lab-prueba"},
            ("PC1", "SW1", "link-1"),
        ),
        ("gns3://templates", {}, ("pfSense", "VPCS")),
    ],
)
@requires_resources
def test_resources_devuelven_datos_legibles_sin_imprimir(
    uri, kwargs, expected, mcp_api, capsys
):
    result = _call(REGISTERED_RESOURCES[uri].fn, **kwargs)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    text = _text(result)
    assert text.strip()
    for value in expected:
        assert value in text


@requires_resources
def test_topologia_inexistente_devuelve_error_con_proyectos_disponibles(mcp_api):
    result = _call(
        REGISTERED_RESOURCES["gns3://project/{project}/topology"].fn,
        project="no-existe",
    )
    text = _text(result)
    folded = _fold(text)
    assert any(message in folded for message in (
        "error", "no existe", "no encontrado", "no se ha encontrado",
    ))
    assert "lab-prueba" in text
    assert "examen-dic" in text


@pytest.mark.parametrize(
    ("name", "kwargs", "required"),
    [
        (
            "gns3-diagnostico",
            {"proyecto": "lab-prueba"},
            ("doctor", "topologia", "consola", "monitor", "ocr", "ping"),
        ),
        (
            "gns3-examen",
            {"servidor": "clase"},
            (
                "arrancar", "pantalla", "interfaces", "vlan", "verificar",
                "portar", "~/GNS3/CHULETA.md",
            ),
        ),
    ],
)
@requires_prompts
def test_prompts_no_incluyen_credenciales_ni_rutas_de_usuario(
    name, kwargs, required, monkeypatch
):
    secrets = ("usuario-contrato", "clave-contrato")
    conf = {"user": secrets[0], "password": secrets[1]}
    monkeypatch.setattr(server, "_conf", lambda: conf)
    monkeypatch.setenv("GNS3_USER", secrets[0])
    monkeypatch.setenv("GNS3_PASSWORD", secrets[1])

    text = _text(_call(REGISTERED_PROMPTS[name].fn, **kwargs))
    folded = _fold(text)
    for value in required:
        assert _fold(value) in folded
    for secret in secrets:
        assert secret not in text
    assert str(Path.home()) not in text
    assert not re.search(
        r"(?i)(?:/home/|/users/|/root/|[a-z]:[\\/]users[\\/])", text
    )
    assert not any(path in text for path in ("~/.config", "~/.ssh", "~/.local"))
    assert not re.search(r"https?://[^/\s:@]+:[^/@\s]+@", text)
    assert not re.search(r"\bbasic\s+[a-z0-9+/=]{8,}", folded)
    assert not re.search(
        r"\b(?:password|passwd|pwd|username|user|usuario|contrasena|clave)"
        r"\s*[:=]\s*[\"']?(?![<{$])[^\s\"',;]+",
        folded,
    )
