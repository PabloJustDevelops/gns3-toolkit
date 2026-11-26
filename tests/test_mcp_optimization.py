"""Contrato de optimización del MCP: elección de tool, errores accionables y caché.

No habla con un GNS3 real: usa el doble HTTP de `conftest` y puertos cerrados.
"""
from __future__ import annotations

import asyncio
import configparser
import inspect
import json
import threading

import pytest
import httpx

import gns3_mcp_server as server

TOOLS_CONTRATO = {
    "gns3_status", "gns3_projects", "gns3_pfsense", "gns3_templates", "gns3_template",
    "gns3_nodes", "gns3_nodes_bulk", "gns3_links", "gns3_link_edit", "gns3_topology",
    "gns3_console", "gns3_console_control", "gns3_capture", "gns3_nio",
    "gns3_port_capture", "gns3_snapshots", "gns3_images", "gns3_node_files",
    "gns3_server_paths", "gns3_exec", "gns3_monitor", "gns3_node_edit", "gns3_upload",
    "gns3_drawings", "gns3_project_io", "gns3_project_stats", "gns3_project_files",
    "gns3_compute", "gns3_statistics", "gns3_symbols", "gns3_appliances",
    "gns3_node_action", "gns3_command_line", "gns3_gns3vm", "gns3_events_url",
    "gns3_events", "gns3_notifications", "gns3_iou_license", "gns3_server",
    "gns3_emulator", "gns3_batch", "gns3_informe", "gns3_link_get", "gns3_drawing_get",
    "gns3_verify", "gns3_project_file_list", "gns3_compute_endpoint",
    "gns3_compute_download", "gns3_lab",
}

# Pares que un LLM confunde al elegir: cada descripción debe remitir a la otra.
CRUZADAS = {
    "gns3_links": "gns3_link_edit",
    "gns3_link_edit": "gns3_links",
    "gns3_templates": "gns3_template",
    "gns3_template": "gns3_templates",
    "gns3_nodes": "gns3_node_action",
    "gns3_node_action": "gns3_nodes_bulk",
    "gns3_nodes_bulk": "gns3_node_action",
    "gns3_console": "gns3_exec",
    "gns3_exec": "gns3_monitor",
    "gns3_monitor": "gns3_exec",
    "gns3_capture": "gns3_port_capture",
    "gns3_port_capture": "gns3_capture",
    "gns3_node_files": "gns3_project_files",
    "gns3_project_files": "gns3_node_files",
    "gns3_images": "gns3_templates",
    "gns3_statistics": "gns3_status",
}

TIPO_RE = ("lectura", "escritura", "mixta")


@pytest.fixture(scope="module")
def tools() -> dict:
    return {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}


def _texto(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


# ─────────────────────── 1. contrato público y descripciones ───────────────────────
def test_el_contrato_publico_sigue_intacto(tools):
    assert set(tools) == TOOLS_CONTRATO
    recursos = asyncio.run(server.mcp.list_resources())
    plantillas = asyncio.run(server.mcp.list_resource_templates())
    prompts = asyncio.run(server.mcp.list_prompts())
    assert {str(r.uri) for r in recursos} == {
        "gns3://status", "gns3://projects", "gns3://templates",
        "gns3://lab/desired", "gns3://lab/actual", "gns3://lab/diff"}
    assert {t.uri_template for t in plantillas} == {"gns3://project/{project}/topology"}
    assert {p.name for p in prompts} == {"gns3-diagnostico", "gns3-examen"}


def test_cada_tool_abre_con_una_frase_de_decision(tools):
    sin_decision = {}
    demasiado_larga = {}
    for nombre, tool in tools.items():
        primera = (tool.description or "").strip().splitlines()[0]
        if "úsala" not in primera.lower():
            sin_decision[nombre] = primera[:120]
        if len(primera) > 220:
            demasiado_larga[nombre] = len(primera)
    assert not sin_decision, sin_decision
    assert not demasiado_larga, demasiado_larga


def test_cada_descripcion_declara_si_lee_o_escribe(tools):
    sin_tipo = {
        nombre: (tool.description or "").splitlines()[0]
        for nombre, tool in tools.items()
        if not any(tipo in (tool.description or "").lower() for tipo in TIPO_RE)
    }
    assert not sin_tipo, sin_tipo


def test_las_descripciones_remiten_a_la_tool_hermana(tools):
    faltan = {
        nombre: hermana
        for nombre, hermana in CRUZADAS.items()
        if hermana not in (tools[nombre].description or "")
    }
    assert not faltan, faltan


def test_las_tools_con_confirm_lo_documentan(tools):
    registradas = server._registered_tool_functions()
    con_confirm = {
        nombre for nombre, fn in registradas.items()
        if "confirm" in inspect.signature(fn).parameters
    }
    assert con_confirm, "ninguna tool declara confirm"
    sin_documentar = {
        nombre for nombre in con_confirm
        if "confirm" not in (tools[nombre].description or "")
    }
    assert not sin_documentar, sin_documentar


# ───────────────────────────── 2. errores accionables ─────────────────────────────
def test_error_de_conexion_explica_como_corregirlo(monkeypatch):
    monkeypatch.setattr(server, "_conf", lambda: {
        "url": "http://127.0.0.1:1", "user": "u", "password": "clave-de-prueba-1234"})

    resultado = server._api("GET", "/v2/version", timeout=1)
    texto = _texto(resultado)

    assert "no se pudo conectar" in resultado["error"]
    assert "GNS3_URL" in resultado["hint"]
    assert "gns3_server.conf" in resultado["hint"]
    assert "clave-de-prueba-1234" not in texto
    assert "Traceback" not in texto


def test_error_401_indica_donde_estan_las_credenciales():
    resultado = server._err_msg(401, {"message": "Unauthorized"}, "listar plantillas")
    texto = _texto(resultado)

    assert "[401]" in resultado["error"]
    assert "GNS3_USER" in resultado.get("hint", "")
    assert "Traceback" not in texto


@pytest.mark.parametrize("nombre, extra", [
    ("gns3_nodes_bulk", {}),
    ("gns3_pfsense", {}),
    ("gns3_project_files", {"path": "x"}),
    ("gns3_compute", {}),
    ("gns3_events", {}),
    ("gns3_server", {}),
])
def test_accion_desconocida_lista_las_validas(nombre, extra, tools):
    fn = server._registered_tool_functions()[nombre]
    resultado = fn(action="nope", **extra)
    validas = resultado.get("valid")
    descripcion = tools[nombre].description or ""

    assert validas, resultado
    assert resultado.get("hint"), resultado
    assert all(str(accion) in descripcion for accion in validas), validas


def test_proyecto_inexistente_sugiere_listar_los_proyectos(fake_api, monkeypatch):
    proyecto = {"project_id": "pid-1", "name": "lab-prueba", "status": "opened"}
    monkeypatch.setattr(server, "_conf", lambda: {
        "url": fake_api.url, "user": "u", "password": "p", "host": "127.0.0.1"})
    fake_api.set_projects([proyecto])

    resultado = server.gns3_topology(project_name="no-existe")
    texto = _texto(resultado)

    assert "proyecto no encontrado" in texto
    assert "gns3_projects" in resultado.get("hint", "")
    assert "lab-prueba" in resultado.get("available", [])
    assert "Traceback" not in texto


# ───────────────────────────── 3. caché y trabajo evitado ─────────────────────────────
def test_conf_lee_el_fichero_una_vez_y_se_invalida_al_cambiar(tmp_path, monkeypatch):
    conf = tmp_path / "gns3_server.conf"
    conf.write_text("[Server]\nuser = admin\npassword = uno\n", encoding="utf-8")
    monkeypatch.setattr(server, "CONF", conf)
    for variable in ("GNS3_URL", "GNS3_USER", "GNS3_PASSWORD"):
        monkeypatch.delenv(variable, raising=False)

    lecturas = []
    original = configparser.ConfigParser.read

    def contar(self, *args, **kwargs):
        lecturas.append(args)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(configparser.ConfigParser, "read", contar)

    primero = server._conf()
    segundo = server._conf()
    assert primero["password"] == segundo["password"] == "uno"
    assert len(lecturas) == 1

    primero["password"] = "mutado"
    assert server._conf()["password"] == "uno"

    conf.write_text("[Server]\nuser = admin\npassword = dos-distinto\n", encoding="utf-8")
    assert server._conf()["password"] == "dos-distinto"
    assert len(lecturas) == 2


def test_conf_respeta_el_entorno_sin_releer_el_fichero(tmp_path, monkeypatch):
    conf = tmp_path / "gns3_server.conf"
    conf.write_text("[Server]\nport = 3080\n", encoding="utf-8")
    monkeypatch.setattr(server, "CONF", conf)
    monkeypatch.delenv("GNS3_URL", raising=False)

    assert server._conf()["url"] == "http://127.0.0.1:3080"

    monkeypatch.setenv("GNS3_URL", "http://10.0.0.5:9999")
    assert server._conf()["url"] == "http://10.0.0.5:9999"


def test_registro_real_coincide_con_list_tools(tools):
    assert set(server._registered_tool_functions()) == set(tools)


def test_el_registro_de_tools_no_se_recalcula_en_cada_lote(monkeypatch):
    llamadas = []
    monkeypatch.setattr(server, "_scan_tool_functions",
                        lambda: llamadas.append(1) or {"api": object()})
    monkeypatch.setattr(server, "_tool_registry", None)

    primero = server._registered_tool_functions()
    segundo = server._registered_tool_functions()

    assert primero is segundo
    assert len(llamadas) == 1


def test_el_cliente_http_se_reutiliza_por_url_y_credenciales(monkeypatch):
    monkeypatch.setattr(server, "_http_clients", {})

    uno = server._http_client("http://127.0.0.1:9", ("u", "p"))
    dos = server._http_client("http://127.0.0.1:9", ("u", "p"))
    otra = server._http_client("http://127.0.0.1:9", ("u", "otra"))

    assert uno is dos
    assert otra is not uno


def test_una_conexion_muerta_del_pool_se_reintenta_una_vez(monkeypatch):
    intentos = []

    class Respuesta:
        status_code = 200
        content = b'{"ok": true}'
        text = '{"ok": true}'

        def json(self):
            return {"ok": True}

    class ClienteMuerto:
        def request(self, *_args, **_kwargs):
            intentos.append(1)
            if len(intentos) == 1:
                raise httpx.RemoteProtocolError("conexion cerrada por el servidor")
            return Respuesta()

    monkeypatch.setattr(server, "_http_client", lambda _url, _auth: ClienteMuerto())
    monkeypatch.setattr(server, "_conf", lambda: {
        "url": "http://127.0.0.1:1", "user": "u", "password": "p"})

    assert server._api("GET", "/v2/projects") == {"ok": True}
    assert len(intentos) == 2


def test_lecturas_concurrentes_usan_el_pool_sin_romperse(fake_api, monkeypatch):
    monkeypatch.setattr(server, "_conf", lambda: {
        "url": fake_api.url, "user": "u", "password": "p", "host": "127.0.0.1"})
    fake_api.set_projects([{"project_id": "p1", "name": "lab-prueba", "status": "opened"}])

    errores = []

    def leer():
        resultado = server._api("GET", "/v2/projects", timeout=5)
        if not isinstance(resultado, list):
            errores.append(resultado)

    hilos = [threading.Thread(target=leer) for _ in range(8)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=10)

    assert not errores
    assert len(fake_api.requests) == 8
