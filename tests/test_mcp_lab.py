"""Contrato de resources y tool `gns3_lab`, sin servidor GNS3."""
from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path

import gns3_mcp_server as server

REPO = Path(__file__).resolve().parents[1]
EJEMPLO = REPO / "examples" / "lab-ejemplo.yaml"
LAB_RESOURCES = (
    "gns3://lab/desired",
    "gns3://lab/actual",
    "gns3://lab/diff",
)
BASE_TOOLS = 49


def _resources() -> dict[str, object]:
    return {str(recurso.uri): recurso
            for recurso in asyncio.run(server.mcp.list_resources())}


def _call(fn, *args, **kwargs):
    resultado = fn(*args, **kwargs)
    return asyncio.run(resultado) if inspect.isawaitable(resultado) else resultado


def _payload(value):
    return json.loads(value) if isinstance(value, str) else value


def test_contrato_resources_y_tool_de_lab_presentes():
    assert set(LAB_RESOURCES) <= _resources().keys()
    tools = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
    assert "gns3_lab" in tools
    assert callable(getattr(server, "gns3_lab", None))


def test_list_resources_incluye_los_tres_recursos_de_lab():
    assert set(LAB_RESOURCES) <= _resources().keys()


def test_list_tools_crece_en_uno_con_gns3_lab():
    tools = asyncio.run(server.mcp.list_tools())

    assert len(tools) == BASE_TOOLS + 1 == 50
    assert {"gns3_lab", "gns3_capturas"} <= {tool.name for tool in tools}


def test_gns3_lab_apply_sin_yes_no_escribe(monkeypatch):
    labspec = server._labspec_module()

    def prohibido(*_args, **_kwargs):
        raise AssertionError("gns3_lab apply sin yes no debe ejecutar ni llamar a la API")

    monkeypatch.setattr(labspec, "ejecutar", prohibido)
    monkeypatch.setattr(server, "_api", prohibido)

    resultado = server.gns3_lab(action="apply", spec=str(EJEMPLO))

    assert resultado["ok"] is False
    assert resultado["plan"]
    assert "yes" in resultado["error"].lower()


def test_gns3_lab_apply_rechaza_un_servidor_ajeno():
    resultado = server.gns3_lab(action="apply", spec=str(EJEMPLO), server="otro")

    assert resultado["ok"] is False
    assert resultado["error"] == (
        "gns3_lab apply solo opera en el servidor del MCP; "
        "usa gns3lab lab apply --server para otro"
    )
    assert "plan" not in resultado


def test_lab_action_error_redacta_detail_anidado(monkeypatch):
    secreto = "clave-falsa-dclfix-9f4c2a"
    monkeypatch.setenv("GNS3_PASSWORD", secreto)
    monkeypatch.setattr(server, "_conf", lambda: {})
    error = {
        "error": "fallo al leer la topología",
        "detail": {
            "url": f"http://usuario:{secreto}@127.0.0.1:3080",
            "attempts": [{"password": secreto}, (secreto,)],
        },
    }

    resultado = server._lab_action_error("diff", error)
    texto = json.dumps(resultado, ensure_ascii=False)

    assert secreto not in texto
    assert "[redactado]" in texto
    assert resultado["detail"]["attempts"][1] == ("[redactado]",)


def test_gns3_lab_diff_funciona_sin_gns3_lab_spec(monkeypatch):
    monkeypatch.delenv("GNS3_LAB_SPEC", raising=False)

    def prohibido(*_args, **_kwargs):
        raise AssertionError("gns3_lab diff con topology no debe llamar a la API")

    monkeypatch.setattr(server, "_api", prohibido)

    resultado = server.gns3_lab(
        action="diff",
        spec=str(EJEMPLO),
        topology={"project": "lab-ejemplo", "nodes": [], "links": []},
    )

    assert "error" not in resultado
    datos = resultado.get("data", resultado)
    assert [nodo["name"] for nodo in datos["crear_nodos"]] == ["pc1", "pc2", "sw1"]


def test_resource_desired_sin_variable_devuelve_error_y_hint(monkeypatch):
    monkeypatch.delenv("GNS3_LAB_SPEC", raising=False)
    recurso = _resources()["gns3://lab/desired"]

    resultado = _payload(_call(recurso.fn))

    assert resultado["error"]
    assert resultado["hint"] == "define GNS3_LAB_SPEC"
