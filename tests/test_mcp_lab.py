"""Contrato de resources y tool `gns3_lab`, sin servidor GNS3."""
from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path

import pytest

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


def test_project_io_export_rearranca_por_nodo_y_verifica_http(monkeypatch, tmp_path):
    """Hallazgo 3: parar nodos antes del try, rearrancar en bucle sin aislar, ignorar HTTP."""
    eventos = []

    class FakeClient:
        def nodes(self, pid):
            return [
                {"node_id": "n1", "name": "N1", "status": "started"},
                {"node_id": "n2", "name": "N2", "status": "started"},
                {"node_id": "n3", "name": "N3", "status": "started"},
                {"node_id": "n4", "name": "N4", "status": "stopped"},
            ]

        def post(self, url, body=None, timeout=None):
            eventos.append(("post", url))
            if url.endswith("/n3/stop"):
                return (500, {"message": "no se pudo parar"})  # n3 no se paró
            if url.endswith("/n1/start"):
                return (500, {"message": "no se pudo rearrancar"})  # falla un restart
            return (200, {})

        def get(self, url, raw=False, timeout=None):
            eventos.append(("get", url))
            return (200, b"PK\x03\x04resto")

    monkeypatch.setattr(server, "_client", lambda: FakeClient())
    monkeypatch.setattr(server, "_pid_or_error", lambda *a, **k: ({"project_id": "p1", "name": "lab"}, None))
    monkeypatch.setattr(server.time, "sleep", lambda _s: None)
    dest = tmp_path / "lab.gns3p"

    with pytest.raises(RuntimeError, match="rearrancar"):
        server.gns3_project_io(action="export", project_id="p1", path=str(dest))

    posts = [url for kind, url in eventos if kind == "post"]
    # n3 no se paró (HTTP 500) -> no se intenta rearrancar
    assert not any(u.endswith("/n3/start") for u in posts)
    # n3 nunca recibió stop exitoso
    # rearranque por nodo aislado: n2 se rearranca aunque n1 falle
    assert any(u.endswith("/n1/start") for u in posts)
    assert any(u.endswith("/n2/start") for u in posts)
    # n4 no estaba started -> no se toca
    assert not any(u.endswith("/n4/start") for u in posts)
    assert not any(u.endswith("/n4/stop") for u in posts)
    # los nodos se paran antes de exportar
    export_idx = next(i for i, e in enumerate(eventos) if e[0] == "get" and e[1].endswith("/export"))
    assert any(e[0] == "post" and e[1].endswith("/n1/stop") for e in eventos[:export_idx])
    assert any(e[0] == "post" and e[1].endswith("/n2/stop") for e in eventos[:export_idx])


def test_project_io_import_no_exige_proyecto_previo(monkeypatch, tmp_path):
    """Hallazgo 5: `import` crea proyecto nuevo; no debe resolver/abrir uno previo."""
    src = tmp_path / "lab.gns3p"
    src.write_bytes(b"PK\x03\x04resto")
    llamadas = {"req": None}

    class FakeClient:
        def req(self, method, url, data=None, ctype=None, timeout=None):
            llamadas["req"] = (method, url)
            return (201, {"name": "importado", "project_id": "nuevo"})

        def put(self, url, body):
            return (200, {})

        def post(self, url, body=None, timeout=None):
            return (200, {})

        def nodes(self, pid):
            return []

    def prohibido(*_a, **_k):
        raise AssertionError("_pid_or_error no debe llamarse para import")

    monkeypatch.setattr(server, "_client", lambda: FakeClient())
    monkeypatch.setattr(server, "_pid_or_error", prohibido)

    resultado = server.gns3_project_io(action="import", path=str(src), open_after=False)

    assert resultado["project_id"]
    assert resultado["name"] == "importado"
    assert llamadas["req"][0] == "POST"
    assert llamadas["req"][1].endswith("/import")


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


def test_lab_redact_ordena_secretos_mas_largos_primero_sin_residuos(monkeypatch):
    """Hallazgo 2: redactar usuario antes que contraseña dejaba sufijos."""
    monkeypatch.setenv("GNS3_USER", "secreto")
    monkeypatch.setenv("GNS3_PASSWORD", "secreto-clave-falsa-9f4c2a")
    monkeypatch.delenv("PFSENSE_USER", raising=False)
    monkeypatch.delenv("PFSENSE_PASSWORD", raising=False)
    monkeypatch.setattr(server, "_conf", lambda: {"user": "", "password": ""})
    texto = "fallo con secreto-clave-falsa-9f4c2a y usuario secreto"

    resultado = server._lab_redact(texto)

    assert "secreto" not in resultado
    assert "secreto-clave-falsa-9f4c2a" not in resultado
    assert "clave-falsa-9f4c2a" not in resultado
    assert "-clave-falsa" not in resultado


def test_lab_redact_conf_ordena_usuario_y_password_sin_residuos(monkeypatch):
    monkeypatch.delenv("GNS3_USER", raising=False)
    monkeypatch.delenv("GNS3_PASSWORD", raising=False)
    monkeypatch.delenv("PFSENSE_USER", raising=False)
    monkeypatch.delenv("PFSENSE_PASSWORD", raising=False)
    monkeypatch.setattr(server, "_conf", lambda: {"user": "admin", "password": "admin12345"})
    texto = "http://admin:admin12345@127.0.0.1:3080 y password admin12345"

    resultado = server._lab_redact(texto)

    assert "admin12345" not in resultado
    assert "12345" not in resultado
    # el usuario suelto también se redige
    assert "admin" not in resultado.replace("[redactado]", "")


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
