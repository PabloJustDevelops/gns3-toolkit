"""Métodos de la GUI portados a la API v2, contra el servidor falso."""
import pytest

from gns3core import Client

P1 = "p1"
N1 = "n1"
L1 = "l1"
T1 = "t1"
C1 = "c1"


# Cada tupla fija método, argumentos, petición HTTP y respuesta esperada. Las
# operaciones que sólo delegan en get/post/put/delete comparten estas pruebas.
GUI_CASES = [
    pytest.param("node_resize_disk", (P1, N1, 128), "POST",
                 f"/v2/projects/{P1}/nodes/{N1}/resize_disk",
                 b'{"hda_disk_size": 128}', {"hda_disk_size": 128}, False,
                 id="node_resize_disk"),
    pytest.param("console_reset", (P1, N1), "POST",
                 f"/v2/projects/{P1}/nodes/{N1}/console/reset",
                 b"", {"status": "reset"}, False, id="console_reset"),
    pytest.param("node_idlepc", (P1, N1), "GET",
                 f"/v2/projects/{P1}/nodes/{N1}/dynamips/auto_idlepc",
                 b"", {"idlepc": "0x1234"}, False, id="node_idlepc_auto"),
    pytest.param("node_idlepc", (P1, N1, True), "GET",
                 f"/v2/projects/{P1}/nodes/{N1}/dynamips/idlepc_proposals",
                 b"", [{"idlepc": "0x1234"}], False, id="node_idlepc_proposals"),
    pytest.param("link_available_filters", (P1, L1), "GET",
                 f"/v2/projects/{P1}/links/{L1}/available_filters",
                 b"", [{"name": "acl"}], False, id="link_available_filters"),
    pytest.param("project_stats", (P1,), "GET", f"/v2/projects/{P1}/stats",
                 b"", {"nodes": 2}, False, id="project_stats"),
    pytest.param("project_load", ("/tmp/lab.gns3",), "POST", "/v2/projects/load",
                 b'{"path": "/tmp/lab.gns3"}', {"project_id": P1}, False,
                 id="project_load"),
    pytest.param("project_file_write", (P1, "config.txt", "hola\n"), "POST",
                 f"/v2/projects/{P1}/files/config.txt", b"hola\n", {"ok": True},
                 False, id="project_file_write"),
    pytest.param("compute_create", ({"compute_id": C1, "name": "remoto"},), "POST",
                 "/v2/computes", b'{"compute_id": "c1", "name": "remoto"}',
                 {"compute_id": C1}, False, id="compute_create"),
    pytest.param("compute_update", (C1, {"name": "renombrado"}), "PUT",
                 f"/v2/computes/{C1}", b'{"name": "renombrado"}',
                 {"compute_id": C1, "name": "renombrado"}, False,
                 id="compute_update"),
    pytest.param("compute_delete", (C1,), "DELETE", f"/v2/computes/{C1}",
                 b"", {"ok": True}, False, id="compute_delete"),
    pytest.param("compute_ports", (C1,), "GET", f"/v2/computes/{C1}/ports",
                 b"", [{"port_number": 1}], False, id="compute_ports"),
    pytest.param("compute_auto_idlepc", (C1,), "POST", f"/v2/computes/{C1}/auto_idlepc",
                 b"", {"status": "started"}, False, id="compute_auto_idlepc"),
    pytest.param("compute_action", (C1, "qemu", "img", {}), "POST",
                 f"/v2/computes/{C1}/qemu/img", b"{}", {"ok": True}, False,
                 id="compute_action_con_body_vacio"),
    pytest.param("compute_action", (C1, "qemu", "binaries", {"action": "create"}),
                 "POST", f"/v2/computes/{C1}/qemu/binaries",
                 b'{"action": "create"}', {"ok": True}, False,
                 id="compute_action_con_body"),
    pytest.param("compute_action", (C1, "qemu", "binaries"), "GET",
                 f"/v2/computes/{C1}/qemu/binaries", b"", {"binaries": []}, False,
                 id="compute_action_sin_body"),
    pytest.param("gns3vm", (), "GET", "/v2/gns3vm", b"", {"engine": "vmware"},
                 False, id="gns3vm"),
    pytest.param("gns3vm_update", ({"name": "vm-nueva"},), "PUT", "/v2/gns3vm",
                 b'{"name": "vm-nueva"}', {"name": "vm-nueva"}, False,
                 id="gns3vm_update"),
    pytest.param("gns3vm_engines", (), "GET", "/v2/gns3vm/engines", b"",
                 [{"engine": "vmware"}], False, id="gns3vm_engines"),
    pytest.param("gns3vm_vms", ("vmware",), "GET", "/v2/gns3vm/engines/vmware/vms",
                 b"", [{"name": "vm1"}], False, id="gns3vm_vms"),
    pytest.param("notifications", (), "GET", "/v2/notifications", b"",
                 [{"text": "global"}], False, id="notifications_globales"),
    pytest.param("notifications", (P1,), "GET", f"/v2/projects/{P1}/notifications",
                 b"", [{"text": "proyecto"}], False, id="notifications_proyecto"),
    pytest.param("template_duplicate", (T1, "copia"), "POST",
                 f"/v2/templates/{T1}/duplicate", b'{"name": "copia"}',
                 {"template_id": "t2"}, False, id="template_duplicate_con_nombre"),
    pytest.param("template_duplicate", (T1,), "POST", f"/v2/templates/{T1}/duplicate",
                 b"{}", {"template_id": "t2"}, False,
                 id="template_duplicate_sin_nombre"),
    pytest.param("template_base_configs", (), "GET", "/v2/templates/base-configs",
                 b"", [{"name": "ios.config"}], False, id="template_base_configs"),
    pytest.param("template_base_config", (T1, "startup.vpc", "hostname R1\n"), "PUT",
                 f"/v2/templates/{T1}/base-config/startup.vpc",
                 b'{"content": "hostname R1\\n"}', {"ok": True}, False,
                 id="template_base_config_escritura"),
    pytest.param("symbol_dimensions", ("router",), "GET", "/v2/symbols/router/dimensions",
                 b"", {"width": 64, "height": 48}, False, id="symbol_dimensions"),
    pytest.param("symbol_raw", ("router",), "GET", "/v2/symbols/router/raw",
                 b"", b"SVG-BYTES", True, id="symbol_raw"),
    pytest.param("symbol_raw_upload", ("router", b"\x89PNG\r\n"), "POST",
                 "/v2/symbols/router/raw", b"\x89PNG\r\n", {"ok": True}, False,
                 id="symbol_raw_upload"),
    pytest.param("default_symbols", (), "GET", "/v2/default_symbols", b"",
                 [{"symbol_id": "router"}], False, id="default_symbols"),
    pytest.param("iou_license", (), "GET", "/v2/iou_license", b"", {"license": "ok"},
                 False, id="iou_license"),
    pytest.param("iou_license_update", ({"license": "nueva"},), "PUT",
                 "/v2/iou_license", b'{"license": "nueva"}', {"license": "nueva"},
                 False, id="iou_license_update"),
    pytest.param("server_shutdown", (), "POST", "/v2/shutdown", b"", {"ok": True},
                 False, id="server_shutdown"),
    pytest.param("server_reload", (), "POST", "/v2/reload", b"", {"ok": True},
                 False, id="server_reload"),
    pytest.param("server_debug", (), "POST", "/v2/debug", b"", {"debug": 1},
                 False, id="server_debug"),
    pytest.param("qemu_binaries", (), "GET", "/v2/computes/local/qemu/binaries", b"",
                 [{"version": "9.0.0"}], False, id="qemu_binaries"),
    pytest.param("qemu_capabilities", (), "GET", "/v2/computes/local/qemu/capabilities",
                 b"", {"kvm": True}, False, id="qemu_capabilities"),
    pytest.param("docker_images", (), "GET", "/v2/computes/local/docker/images", b"",
                 [{"image": "alpine"}], False, id="docker_images"),
    pytest.param("network_interfaces", (), "GET", "/v2/computes/local/network/interfaces",
                 b"", [{"name": "eth0"}], False, id="network_interfaces"),
    pytest.param("network_ports", (), "GET", "/v2/computes/local/network/ports", b"",
                 [{"port": 3080}], False, id="network_ports"),
    pytest.param("udp_port", (5000,), "POST", "/v2/computes/local/ports/udp",
                 b'{"port": 5000}', {"port": 5000}, False, id="udp_port"),
]


@pytest.mark.parametrize(
    ("method", "args", "http_method", "path", "request_body", "response", "raw_response"),
    GUI_CASES,
)
def test_operaciones_gui_exito_y_peticion(
        fake_api, method, args, http_method, path, request_body, response, raw_response):
    fake_api.route(http_method, path, 200, response)

    result = getattr(Client(fake_api.url), method)(*args)

    assert result == (200, response)
    req = fake_api.last(http_method, path)
    assert req["body"] == request_body
    if method == "project_file_write":
        assert req["headers"]["content-type"] == "text/plain"
    elif method == "symbol_raw_upload":
        assert req["headers"]["content-type"] == "application/octet-stream"


@pytest.mark.parametrize(
    ("method", "args", "http_method", "path", "request_body", "response", "raw_response"),
    GUI_CASES,
)
def test_operaciones_gui_propagan_http_no_200(
        fake_api, method, args, http_method, path, request_body, response, raw_response):
    error = b'{"message": "conflicto"}' if raw_response else {"message": "conflicto"}
    fake_api.route(http_method, path, 409, error)

    assert getattr(Client(fake_api.url), method)(*args) == (409, error)
    assert fake_api.last(http_method, path)["body"] == request_body


# ─────────────────────────────── consola WebSocket ───────────────────────────
@pytest.mark.parametrize(
    ("detail", "expected"),
    [
        ({"console_url": "wss://servidor/consola"}, "wss://servidor/consola"),
        ({"console_type": "telnet"},
         f"ws://127.0.0.1:3080/v2/projects/{P1}/nodes/{N1}/console/ws"),
        ({"console_type": "vnc"},
         f"ws://127.0.0.1:3080/v2/projects/{P1}/nodes/{N1}/console/ws"),
        ({"console_url": "", "console_type": "telnet"},
         f"ws://127.0.0.1:3080/v2/projects/{P1}/nodes/{N1}/console/ws"),
        ({}, ""),
        ({"console_type": "serial"}, ""),
        (["no", "es", "dict"], ""),
    ],
)
def test_console_ws_url_deriva_la_url_o_devuelve_vacio(fake_api, detail, expected):
    fake_api.route("GET", f"/v2/projects/{P1}/nodes/{N1}", 200, detail)
    assert Client(fake_api.url).console_ws_url(P1, N1) == expected


def test_console_ws_url_propaga_http_no_200(fake_api):
    fake_api.route("GET", f"/v2/projects/{P1}/nodes/{N1}", 404,
                   {"message": "no existe"})
    with pytest.raises(RuntimeError, match=r"\[404\]"):
        Client(fake_api.url).console_ws_url(P1, N1)


# ───────────────────────────────── enlaces ──────────────────────────────────
@pytest.mark.parametrize(
    ("status", "payload", "expected"),
    [
        (200, [{"link_id": L1}], [{"link_id": L1}]),
        (500, {"message": "fallo"}, []),
        (200, {"no": "es lista"}, []),
    ],
)
def test_node_links_tolera_error_y_cuerpo_inesperado(fake_api, status, payload, expected):
    path = f"/v2/projects/{P1}/nodes/{N1}/links"
    fake_api.route("GET", path, status, payload)
    assert Client(fake_api.url).node_links(P1, N1) == expected
    assert fake_api.last("GET", path)


# ───────────────────────── duplicado de proyectos ───────────────────────────
@pytest.mark.parametrize("name", [None, ""])
def test_project_duplicate_sin_nombre_manda_objeto_vacio(fake_api, name):
    path = f"/v2/projects/{P1}/duplicate"
    response = {"project_id": "p2", "name": "lab-copia"}
    fake_api.route("POST", path, 201, response)

    assert Client(fake_api.url).project_duplicate(P1, name) == (201, response)
    assert fake_api.last("POST", path)["body"] == b"{}"
    assert not [r for r in fake_api.requests if r["method"] == "PUT"]


def test_project_duplicate_con_nombre_correcto_no_renombra(fake_api):
    path = f"/v2/projects/{P1}/duplicate"
    response = {"project_id": "p2", "name": "copia"}
    fake_api.route("POST", path, 201, response)

    assert Client(fake_api.url).project_duplicate(P1, "copia") == (201, response)
    assert fake_api.last("POST", path)["body"] == b'{"name": "copia"}'
    assert not [r for r in fake_api.requests if r["method"] == "PUT"]


@pytest.mark.parametrize("status", [200, 201])
def test_project_duplicate_renombra_si_el_servidor_ignora_el_nombre(fake_api, status):
    duplicate_path = f"/v2/projects/{P1}/duplicate"
    update_path = "/v2/projects/p2"
    response = {"project_id": "p2", "name": "lab (copy)"}
    fake_api.route("POST", duplicate_path, status, response)
    fake_api.route("PUT", update_path, 200, {"project_id": "p2", "name": "copia"})

    result = Client(fake_api.url).project_duplicate(P1, "copia")

    assert result == (status, {"project_id": "p2", "name": "copia"})
    assert fake_api.last("PUT", update_path)["body"] == b'{"name": "copia"}'


@pytest.mark.parametrize("response", [{"name": "lab (copy)"}, "texto plano"])
def test_project_duplicate_no_renombra_sin_id_o_con_cuerpo_inesperado(fake_api, response):
    path = f"/v2/projects/{P1}/duplicate"
    fake_api.route("POST", path, 201, response)

    assert Client(fake_api.url).project_duplicate(P1, "copia") == (201, response)
    assert not [r for r in fake_api.requests if r["method"] == "PUT"]


def test_project_duplicate_propaga_error_sin_renombrar(fake_api):
    path = f"/v2/projects/{P1}/duplicate"
    error = {"message": "conflicto", "project_id": "p2", "name": "otro"}
    fake_api.route("POST", path, 409, error)

    assert Client(fake_api.url).project_duplicate(P1, "copia") == (409, error)
    assert not [r for r in fake_api.requests if r["method"] == "PUT"]


# ─────────────────────── ficheros de proyecto y plantillas ───────────────────
def test_project_file_read_decodifica_bytes_y_quita_barra_inicial(fake_api):
    path = f"/v2/projects/{P1}/files/config.txt"
    fake_api.route("GET", path, 200, b"hola\xff")

    assert Client(fake_api.url).project_file_read(P1, "/config.txt") == "hola\ufffd"
    assert fake_api.last("GET", path)


@pytest.mark.parametrize("status", [404, 500])
def test_project_file_read_devuelve_error_http(fake_api, status):
    path = f"/v2/projects/{P1}/files/config.txt"
    fake_api.route("GET", path, status, b"no disponible")
    assert Client(fake_api.url).project_file_read(P1, "config.txt") == {
        "error": f"HTTP {status}",
    }


def test_project_file_read_tolera_cuerpo_no_binario(fake_api, monkeypatch):
    client = Client(fake_api.url)
    monkeypatch.setattr(client, "get", lambda *a, **kw: (200, {"inesperado": True}))
    assert client.project_file_read(P1, "config.txt") == {"error": "HTTP 200"}


def test_template_base_config_lee_y_decodifica_el_contenido(fake_api):
    path = f"/v2/templates/{T1}/base-config/startup.vpc"
    fake_api.route("GET", path, 200, b"hostname R1\n")
    assert Client(fake_api.url).template_base_config(T1, "startup.vpc") == "hostname R1\n"
    assert fake_api.last("GET", path)


def test_template_base_config_lectura_devuelve_error_http(fake_api):
    path = f"/v2/templates/{T1}/base-config/startup.vpc"
    fake_api.route("GET", path, 404, b"no existe")
    assert Client(fake_api.url).template_base_config(T1, "startup.vpc") == {
        "error": "HTTP 404",
    }


def test_template_base_config_tolera_cuerpo_no_binario(fake_api, monkeypatch):
    client = Client(fake_api.url)
    monkeypatch.setattr(client, "get", lambda *a, **kw: (200, {"inesperado": True}))
    assert client.template_base_config(T1, "startup.vpc") == {"error": "HTTP 200"}


def test_template_base_config_escribe_contenido_vacio(fake_api):
    path = f"/v2/templates/{T1}/base-config/startup.vpc"
    fake_api.route("PUT", path, 200, {"ok": True})

    assert Client(fake_api.url).template_base_config(T1, "startup.vpc", "") == (
        200, {"ok": True})
    assert fake_api.last("PUT", path)["body"] == b'{"content": ""}'
