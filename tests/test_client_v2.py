"""Superficie v2 ampliada de `Client` contra la API falsa."""
import base64

import pytest

import gns3core
from gns3core import Client

P1 = "11111111-aaaa-bbbb-cccc-000000000001"


def _project(name="lab", pid=P1, status="opened"):
    return {"name": name, "project_id": pid, "status": status}


# ─────────────────────────────── transporte ───────────────────────────────
def test_version_devuelve_el_dict(fake_api):
    assert Client(fake_api.url).version()["version"] == "2.2.61"


def test_req_manda_basic_auth_cuando_hay_credenciales(fake_api):
    c = Client(fake_api.url, auth=("pablo", "secreto"))
    c.version()
    req = fake_api.last("GET", "/v2/version")
    esperado = base64.b64encode(b"pablo:secreto").decode()
    assert req["headers"]["authorization"] == "Basic " + esperado


def test_json_cae_a_texto_si_el_cuerpo_no_es_json(fake_api):
    fake_api.route("GET", "/v2/version", 200, "no soy json")
    assert Client(fake_api.url).version() == "no soy json"


def test_json_tolera_bytes_que_no_son_utf8(fake_api):
    fake_api.route("GET", "/v2/version", 200, b"\xff\xfe")
    assert Client(fake_api.url).version() == "\ufffd\ufffd"


def test_post_put_delete_serializan_el_payload(fake_api):
    fake_api.route("POST", "/v2/x", 201, {"ok": True})
    fake_api.route("PUT", "/v2/x", 200, {"ok": True})
    fake_api.route("DELETE", "/v2/x", 204, b"")
    c = Client(fake_api.url)

    assert c.post("/v2/x", {"a": 1})[0] == 201
    assert fake_api.last("POST", "/v2/x")["body"] == b'{"a": 1}'
    assert fake_api.last("POST", "/v2/x")["headers"]["content-type"] == "application/json"

    assert c.put("/v2/x", {"b": 2})[0] == 200
    assert fake_api.last("PUT", "/v2/x")["body"] == b'{"b": 2}'

    assert c.delete("/v2/x") == (204, None)


def test_post_sin_payload_manda_cuerpo_vacio(fake_api):
    fake_api.route("POST", "/v2/x", 201, {"ok": True})
    Client(fake_api.url).post("/v2/x")
    req = fake_api.last("POST", "/v2/x")
    assert req["body"] == b""
    assert req["headers"]["content-type"] == "application/json"


# ──────────────────────────────── listados ────────────────────────────────
def test_links_templates_y_qemu_images(fake_api):
    c = Client(fake_api.url)

    fake_api.route("GET", f"/v2/projects/{P1}/links", 200, [{"link_id": "l1"}])
    assert c.links(P1) == [{"link_id": "l1"}]

    fake_api.route("GET", "/v2/templates", 200, [{"template_id": "t1"}])
    assert c.templates() == [{"template_id": "t1"}]

    fake_api.route("GET", "/v2/computes/local/qemu/images", 200, [{"filename": "a.qcow2"}])
    assert c.qemu_images() == [{"filename": "a.qcow2"}]


def test_listados_devuelven_vacio_si_la_api_falla_o_no_es_lista(fake_api):
    c = Client(fake_api.url)

    fake_api.route("GET", f"/v2/projects/{P1}/links", 500, {"message": "boom"})
    assert c.links(P1) == []

    fake_api.route("GET", "/v2/templates", 200, {"no": "es lista"})
    assert c.templates() == []

    fake_api.route("GET", "/v2/computes/local/qemu/images", 200, "texto")
    assert c.qemu_images() == []


def test_computes_estadisticas_simbolos_y_appliances(fake_api):
    c = Client(fake_api.url)
    casos = [
        ("/v2/computes", [{"compute_id": "local"}], c.computes),
        ("/v2/statistics", [{"name": "cpu"}], c.statistics),
        ("/v2/symbols", [{"symbol_id": "router"}], c.symbols),
        ("/v2/appliances", [{"appliance_id": "vpcs"}], c.appliances),
    ]
    for path, payload, fn in casos:
        fake_api.route("GET", path, 200, payload)
        assert fn() == payload


def test_computes_devuelve_vacio_si_falla(fake_api):
    fake_api.route("GET", "/v2/computes", 500, {"message": "boom"})
    assert Client(fake_api.url).computes() == []


@pytest.mark.parametrize(
    ("method", "args", "path", "raises"),
    [
        ("projects", (), "/v2/projects", True),
        ("nodes", (P1,), f"/v2/projects/{P1}/nodes", True),
        ("links", (P1,), f"/v2/projects/{P1}/links", False),
        ("templates", (), "/v2/templates", False),
        ("qemu_images", (), "/v2/computes/local/qemu/images", False),
        ("computes", (), "/v2/computes", False),
        ("statistics", (), "/v2/statistics", False),
        ("symbols", (), "/v2/symbols", False),
        ("appliances", (), "/v2/appliances", False),
        ("images", (), "/v2/computes/local/qemu/images", False),
        ("snapshots", ("p1",), "/v2/projects/p1/snapshots", False),
        ("drawings", ("p1",), "/v2/projects/p1/drawings", False),
    ],
)
@pytest.mark.parametrize(
    ("status", "payload"),
    [(500, {"message": "boom"}), (200, {"no": "es una lista"})],
)
def test_listados_ante_error_o_cuerpo_invalido(
        fake_api, method, args, path, raises, status, payload):
    fake_api.route("GET", path, status, payload)
    if status == 500 and raises:
        with pytest.raises(RuntimeError, match=r"\[500\]"):
            getattr(Client(fake_api.url), method)(*args)
    else:
        assert getattr(Client(fake_api.url), method)(*args) == []


def test_compute_devuelve_dict_o_none(fake_api):
    c = Client(fake_api.url)
    fake_api.route("GET", "/v2/computes/local", 200, {"compute_id": "local"})
    assert c.compute() == {"compute_id": "local"}

    fake_api.route("GET", "/v2/computes/otro", 404, {"message": "no existe"})
    assert c.compute("otro") is None

    fake_api.route("GET", "/v2/computes/raro", 200, ["no", "es", "dict"])
    assert c.compute("raro") is None


def test_images_acepta_el_sufijo_images(fake_api):
    c = Client(fake_api.url)
    fake_api.route("GET", "/v2/computes/local/qemu/images", 200, [{"filename": "a.qcow2"}])
    assert c.images() == [{"filename": "a.qcow2"}]
    assert c.images("qemu/images") == [{"filename": "a.qcow2"}]


# ───────────────────────────────  proyectos  ───────────────────────────────
def test_project_get_y_errores(fake_api):
    c = Client(fake_api.url)
    fake_api.route("GET", f"/v2/projects/{P1}", 200, _project())
    assert c.project_get(P1)["name"] == "lab"

    fake_api.route("GET", "/v2/projects/otro", 404, {"message": "no existe"})
    with pytest.raises(RuntimeError, match=r"\[404\]"):
        c.project_get("otro")


def test_project_close_y_delete(fake_api):
    c = Client(fake_api.url)
    fake_api.route("POST", f"/v2/projects/{P1}/close", 201, {"status": "closed"})
    assert c.project_close(P1)[0] == 201

    fake_api.route("DELETE", f"/v2/projects/{P1}", 204, b"")
    assert c.project_delete(P1)[0] == 204


def test_project_delete_propaga_error(fake_api):
    fake_api.route("DELETE", f"/v2/projects/{P1}", 409, {"message": "abierto"})
    assert Client(fake_api.url).project_delete(P1) == (409, {"message": "abierto"})


# ─────────────────────────────── plantillas  ───────────────────────────────
def test_template_get_update_delete(fake_api):
    c = Client(fake_api.url)
    tid = "t1"
    fake_api.route("GET", f"/v2/templates/{tid}", 200, {"template_id": tid})
    fake_api.route("PUT", f"/v2/templates/{tid}", 200, {"template_id": tid, "name": "n"})
    fake_api.route("DELETE", f"/v2/templates/{tid}", 204, b"")

    assert c.template_get(tid)[0] == 200
    st, body = c.template_update(tid, {"name": "n"})
    assert st == 200 and body["name"] == "n"
    assert fake_api.last("PUT", f"/v2/templates/{tid}")["body"] == b'{"name": "n"}'
    assert c.template_delete(tid)[0] == 204


# ────────────────────────────────  nodos  ────────────────────────────────
@pytest.mark.parametrize("action", ["start", "stop", "reload", "suspend"])
def test_node_action_valida_manda_el_post(fake_api, action):
    path = f"/v2/projects/p1/nodes/n1/{action}"
    fake_api.route("POST", path, 200, {"status": action})
    st, body = Client(fake_api.url).node_action("p1", "n1", action)
    assert st == 200 and body == {"status": action}
    assert fake_api.last("POST", path)


def test_node_action_desconocida_lanza_valueerror():
    with pytest.raises(ValueError, match="acción de nodo desconocida: reboot"):
        Client("http://127.0.0.1:1").node_action("p1", "n1", "reboot")


def test_node_command_line_lee_el_detalle(fake_api):
    c = Client(fake_api.url)
    fake_api.route("GET", "/v2/projects/p1/nodes/n1", 200,
                   {"name": "R1", "command_line": "-m 512M"})
    assert c.node_command_line("p1", "n1") == "-m 512M"


def test_node_command_line_vacio_si_el_detalle_no_es_dict(fake_api):
    fake_api.route("GET", "/v2/projects/p1/nodes/n1", 200, ["no", "es", "dict"])
    assert Client(fake_api.url).node_command_line("p1", "n1") == ""


# ──────────────────────────────── enlaces  ────────────────────────────────
def test_link_update_y_delete(fake_api):
    c = Client(fake_api.url)
    fake_api.route("PUT", "/v2/projects/p1/links/l1", 200, {"link_id": "l1", "filters": {}})
    fake_api.route("DELETE", "/v2/projects/p1/links/l1", 204, b"")

    assert c.link_update("p1", "l1", {"filters": {}})[0] == 200
    assert fake_api.last("PUT", "/v2/projects/p1/links/l1")["body"] == '{"filters": {}}'.encode()
    assert c.link_delete("p1", "l1")[0] == 204


def test_link_capture_start_usa_el_nombre_por_defecto(fake_api):
    path = "/v2/projects/p1/links/abcdefgh-0000/start_capture"
    fake_api.route("POST", path, 200, {"status": "started"})
    st, _ = Client(fake_api.url).link_capture("p1", "abcdefgh-0000", "start")
    assert st == 200
    body = fake_api.last("POST", path)["body"]
    assert body == (b'{"data_link_type": "DLT_EN10MB", '
                    b'"capture_file_name": "capture-abcdefgh.pcap"}')


def test_link_capture_start_acepta_nombre_explicito(fake_api):
    path = "/v2/projects/p1/links/l1/start_capture"
    fake_api.route("POST", path, 200, {"status": "started"})
    Client(fake_api.url).link_capture("p1", "l1", "start", file_name="mio.pcap")
    assert b'"capture_file_name": "mio.pcap"' in fake_api.last("POST", path)["body"]


def test_link_capture_stop_y_pcap(fake_api):
    c = Client(fake_api.url)
    fake_api.route("POST", "/v2/projects/p1/links/l1/stop_capture", 200, {"status": "stopped"})
    fake_api.route("GET", "/v2/projects/p1/links/l1/pcap", 200, b"PCAP-BYTES")

    assert c.link_capture("p1", "l1", "stop")[0] == 200
    st, body = c.link_capture("p1", "l1", "pcap")
    assert st == 200 and body == b"PCAP-BYTES"


def test_link_capture_desconocida_lanza_valueerror():
    with pytest.raises(ValueError, match="acción de captura desconocida: dump"):
        Client("http://127.0.0.1:1").link_capture("p1", "l1", "dump")


# ──────────────────────────────── dibujos  ────────────────────────────────
def test_drawings_y_drawing_create(fake_api):
    c = Client(fake_api.url)
    fake_api.route("GET", "/v2/projects/p1/drawings", 200, [{"drawing_id": "d1"}])
    fake_api.route("POST", "/v2/projects/p1/drawings", 201, {"drawing_id": "d2"})

    assert c.drawings("p1") == [{"drawing_id": "d1"}]
    assert c.drawing_create("p1", {"type": "text"})[0] == 201
    assert fake_api.last("POST", "/v2/projects/p1/drawings")["body"] == b'{"type": "text"}'


def test_drawings_vacio_si_falla(fake_api):
    fake_api.route("GET", "/v2/projects/p1/drawings", 500, {"message": "boom"})
    assert Client(fake_api.url).drawings("p1") == []


def test_drawing_update_y_delete(fake_api):
    c = Client(fake_api.url)
    fake_api.route("PUT", "/v2/projects/p1/drawings/d1", 200, {"drawing_id": "d1"})
    fake_api.route("DELETE", "/v2/projects/p1/drawings/d1", 204, b"")

    assert c.drawing_update("p1", "d1", {"x": 1})[0] == 200
    assert fake_api.last("PUT", "/v2/projects/p1/drawings/d1")["body"] == b'{"x": 1}'
    assert c.drawing_delete("p1", "d1")[0] == 204


# ──────────────────────────────── snapshots ────────────────────────────────
def test_snapshots_y_acciones(fake_api):
    c = Client(fake_api.url)
    fake_api.route("GET", "/v2/projects/p1/snapshots", 200, [{"snapshot_id": "s1"}])
    fake_api.route("POST", "/v2/projects/p1/snapshots", 201, {"snapshot_id": "s2"})
    fake_api.route("POST", "/v2/projects/p1/snapshots/s2/restore", 201, {"status": "restored"})
    fake_api.route("DELETE", "/v2/projects/p1/snapshots/s1", 204, b"")

    assert c.snapshots("p1") == [{"snapshot_id": "s1"}]
    assert c.snapshot_create("p1", "antes-del-cambio")[0] == 201
    assert fake_api.last("POST", "/v2/projects/p1/snapshots")["body"] == \
        b'{"name": "antes-del-cambio"}'
    assert c.snapshot_restore("p1", "s2")[0] == 201
    assert c.snapshot_delete("p1", "s1")[0] == 204


def test_snapshots_vacio_si_falla(fake_api):
    fake_api.route("GET", "/v2/projects/p1/snapshots", 500, {"message": "boom"})
    assert Client(fake_api.url).snapshots("p1") == []


# ────────────────────────────── subida de disco  ──────────────────────────────
def test_compute_write_file_manda_los_bytes_tal_cual(fake_api):
    path = "/v2/computes/local/qemu/images/disco.qcow2"
    fake_api.route("POST", path, 201, {"filename": "disco.qcow2"})
    st, body = Client(fake_api.url).compute_write_file(
        "local", "qemu", "disco.qcow2", b"QFI\xfbcontenido")
    req = fake_api.last("POST", path)
    assert st == 201 and body["filename"] == "disco.qcow2"
    assert req["body"] == b"QFI\xfbcontenido"
    assert req["headers"]["content-type"] == "application/octet-stream"


@pytest.mark.parametrize(
    ("method", "args", "http_method", "path"),
    [
        ("project_close", ("p1",), "POST", "/v2/projects/p1/close"),
        ("project_delete", ("p1",), "DELETE", "/v2/projects/p1"),
        ("template_get", ("t1",), "GET", "/v2/templates/t1"),
        ("template_update", ("t1", {"name": "n"}), "PUT", "/v2/templates/t1"),
        ("template_delete", ("t1",), "DELETE", "/v2/templates/t1"),
        ("node_action", ("p1", "n1", "start"), "POST", "/v2/projects/p1/nodes/n1/start"),
        ("link_update", ("p1", "l1", {"filters": {}}), "PUT", "/v2/projects/p1/links/l1"),
        ("link_delete", ("p1", "l1"), "DELETE", "/v2/projects/p1/links/l1"),
        ("link_capture", ("p1", "l1", "start"), "POST",
         "/v2/projects/p1/links/l1/start_capture"),
        ("link_capture", ("p1", "l1", "stop"), "POST",
         "/v2/projects/p1/links/l1/stop_capture"),
        ("drawing_update", ("p1", "d1", {"x": 1}), "PUT", "/v2/projects/p1/drawings/d1"),
        ("drawing_delete", ("p1", "d1"), "DELETE", "/v2/projects/p1/drawings/d1"),
        ("snapshot_create", ("p1", "s1"), "POST", "/v2/projects/p1/snapshots"),
        ("snapshot_restore", ("p1", "s1"), "POST", "/v2/projects/p1/snapshots/s1/restore"),
        ("snapshot_delete", ("p1", "s1"), "DELETE", "/v2/projects/p1/snapshots/s1"),
        ("drawing_create", ("p1", {"type": "text"}), "POST", "/v2/projects/p1/drawings"),
        ("compute_write_file", ("local", "qemu", "disco.qcow2", b"datos"), "POST",
         "/v2/computes/local/qemu/images/disco.qcow2"),
    ],
)
def test_operaciones_nuevas_propagan_el_error_de_la_api(
        fake_api, method, args, http_method, path):
    fake_api.route(http_method, path, 409, {"message": "conflicto"})
    assert getattr(Client(fake_api.url), method)(*args) == (409, {"message": "conflicto"})
    assert fake_api.last(http_method, path)


def test_link_capture_pcap_propaga_el_error_en_crudo(fake_api):
    path = "/v2/projects/p1/links/l1/pcap"
    fake_api.route("GET", path, 409, b"captura no disponible")
    assert Client(fake_api.url).link_capture("p1", "l1", "pcap") == (
        409, b"captura no disponible")


@pytest.mark.parametrize("method", ["node_detail", "node_command_line"])
def test_consultas_de_nodo_propagan_http_no_200(fake_api, method):
    fake_api.route("GET", "/v2/projects/p1/nodes/n1", 404, {"message": "no existe"})
    with pytest.raises(RuntimeError, match=r"\[404\]"):
        getattr(Client(fake_api.url), method)("p1", "n1")


# ───────────────────────────── ensure_open / nodos ─────────────────────────────
def test_ensure_open_si_ya_esta_abierto_no_manda_open(fake_api):
    fake_api.route("GET", f"/v2/projects/{P1}", 200, {"status": "opened"})
    Client(fake_api.url).ensure_open(P1)
    assert not [r for r in fake_api.requests if r["path"].endswith("/open")]


def test_ensure_open_abre_el_proyecto(fake_api):
    fake_api.route("GET", f"/v2/projects/{P1}", 200, {"status": "closed"})
    fake_api.route("POST", f"/v2/projects/{P1}/open", 201, {"status": "opened"})
    Client(fake_api.url).ensure_open(P1)
    assert fake_api.last("POST", f"/v2/projects/{P1}/open")


def test_ensure_open_reintenta_tras_el_fallo_de_libvirt(fake_api, monkeypatch):
    fake_api.route("GET", f"/v2/projects/{P1}", 200, {"status": "closed"})
    monkeypatch.setattr(gns3core.time, "sleep", lambda *_: None)
    c = Client(fake_api.url)
    llamadas = []

    def fake_post(path, payload=None, **kw):
        llamadas.append(path)
        return (500, {"message": "libvirt"}) if len(llamadas) == 1 else (201, {"status": "opened"})

    monkeypatch.setattr(c, "post", fake_post)
    c.ensure_open(P1)
    assert len(llamadas) == 2


def test_ensure_open_falla_dos_veces_y_describe_el_error(fake_api, monkeypatch):
    fake_api.route("GET", f"/v2/projects/{P1}", 200, {"status": "closed"})
    monkeypatch.setattr(gns3core.time, "sleep", lambda *_: None)
    c = Client(fake_api.url)
    monkeypatch.setattr(c, "post", lambda *a, **k: (500, {"message": "libvirt muerto"}))
    with pytest.raises(RuntimeError, match=r"no abre el proyecto: \[500\] libvirt muerto"):
        c.ensure_open(P1)


def test_ensure_open_falla_con_respuesta_sin_message(fake_api, monkeypatch):
    fake_api.route("GET", f"/v2/projects/{P1}", 200, {"status": "closed"})
    monkeypatch.setattr(gns3core.time, "sleep", lambda *_: None)
    c = Client(fake_api.url)
    monkeypatch.setattr(c, "post", lambda *a, **k: (500, "texto plano"))
    with pytest.raises(RuntimeError, match="texto plano"):
        c.ensure_open(P1)


def test_ensure_open_error_al_leer_el_proyecto(fake_api):
    fake_api.route("GET", f"/v2/projects/{P1}", 404, {"message": "no existe"})
    with pytest.raises(RuntimeError, match=r"proyecto .*\[404\]"):
        Client(fake_api.url).ensure_open(P1)


def test_ensure_open_proyecto_que_no_es_dict(fake_api):
    fake_api.route("GET", f"/v2/projects/{P1}", 200, ["no", "es", "dict"])
    with pytest.raises(RuntimeError, match=r"\[200\]"):
        Client(fake_api.url).ensure_open(P1)


def test_find_node_encuentra_y_si_no_falla(fake_api):
    fake_api.set_nodes(P1, [{"name": "R1", "node_id": "n1"},
                            {"name": "PC1", "node_id": "n2"}])
    c = Client(fake_api.url)
    assert c.find_node(P1, "r1")["node_id"] == "n1"

    with pytest.raises(SystemExit, match="nodo no encontrado: 'SW9'. Hay: R1, PC1"):
        c.find_node(P1, "SW9")


def test_node_detail_pide_el_nodo(fake_api):
    fake_api.route("GET", "/v2/projects/p1/nodes/n1", 200, {"name": "R1"})
    assert Client(fake_api.url).node_detail("p1", "n1") == {"name": "R1"}
