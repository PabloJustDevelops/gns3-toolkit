"""Candidatos con valor del inventario: ficheros de proyecto, compute remoto y endpoint.

Rutas verificadas en la instalación local de gns3server 2.2:

- listado: ``api/compute/project_handler.py:216-233`` (``GET /projects/{id}/files``),
  consumido por el proxy ``GET /v2/computes/{cid}/projects/{id}/files``.
- endpoint: ``api/controller/compute_handler.py:99-125`` (``GET /computes/endpoint/...``),
  que devuelve JSON ``{"endpoint": "<url>"}`` y no un binario.
"""
from __future__ import annotations

import asyncio

import gns3_mcp_server as server
from gns3core import Client

PID = "11111111-aaaa-bbbb-cccc-000000000001"
CID = "compute-remoto"
NID = "22222222-aaaa-bbbb-cccc-000000000002"


# ───────────────────────── listado de ficheros ─────────────────────────
def test_project_file_list_usa_el_proxy_del_compute_y_normaliza(fake_api):
    fake_api.route("GET", f"/v2/computes/{CID}/projects/{PID}/files", 200, [
        {"path": "config.xml", "md5sum": "abc"},
        {"path": "routers/startup-config", "md5sum": "def", "size": 42},
        {"path": "captures/link.pcap", "md5sum": "ghi"},
        "basura",
    ])

    files = Client(fake_api.url).project_file_list(PID, compute_id=CID)

    assert fake_api.last("GET", f"/v2/computes/{CID}/projects/{PID}/files")
    assert files == [
        {"path": "config.xml", "type": "xml", "size": None, "md5sum": "abc"},
        {"path": "routers/startup-config", "type": "file", "size": 42,
         "md5sum": "def"},
        {"path": "captures/link.pcap", "type": "pcap", "size": None, "md5sum": "ghi"},
    ]


def test_project_file_list_filtra_por_prefijo_sin_adivinar(fake_api):
    fake_api.route("GET", f"/v2/computes/local/projects/{PID}/files", 200, [
        {"path": "config.xml", "md5sum": "a"},
        {"path": "routers/router1/startup-config", "md5sum": "b"},
        {"path": "routers/router2/startup-config", "md5sum": "c"},
    ])
    c = Client(fake_api.url)

    assert [f["path"] for f in c.project_file_list(PID, prefix="routers/router1")] == [
        "routers/router1/startup-config"]
    assert [f["path"] for f in c.project_file_list(PID, prefix="/routers/")] == [
        "routers/router1/startup-config", "routers/router2/startup-config"]


def test_project_file_list_devuelve_vacio_si_la_api_falla(fake_api):
    fake_api.route("GET", f"/v2/computes/local/projects/{PID}/files", 404,
                   {"message": "project not found"})
    assert Client(fake_api.url).project_file_list(PID) == []


# ───────────────────────── endpoint de compute ─────────────────────────
def test_compute_endpoint_devuelve_la_url_sin_llamarla(fake_api):
    url = "http://127.0.0.1:3081/v2/compute/projects/p/qemu/images/disco.qcow2"
    fake_api.route("GET", f"/v2/computes/endpoint/{CID}/qemu/images/disco.qcow2", 200,
                   {"endpoint": url})

    st, res = Client(fake_api.url).compute_endpoint(CID, "qemu", "images/disco.qcow2")

    assert (st, res) == (200, {"endpoint": url})
    assert fake_api.last("GET", f"/v2/computes/endpoint/{CID}/qemu/images/disco.qcow2")


# ───────────────────────── compute remoto ─────────────────────────
def test_images_y_qemu_images_aceptan_compute(fake_api):
    fake_api.route("GET", f"/v2/computes/{CID}/qemu/images", 200,
                   [{"filename": "a.qcow2"}])
    fake_api.route("GET", f"/v2/computes/{CID}/docker/images", 200,
                   [{"image": "alpine"}])
    c = Client(fake_api.url)

    assert c.qemu_images(compute_id=CID) == [{"filename": "a.qcow2"}]
    assert c.images("qemu", compute_id=CID) == [{"filename": "a.qcow2"}]
    assert c.images("docker/images", compute_id=CID) == [{"image": "alpine"}]
    assert c.qemu_images() == []


def test_qemu_binaries_acepta_compute(fake_api):
    fake_api.route("GET", f"/v2/computes/{CID}/qemu/binaries", 200,
                   {"version": "9.0.0"})
    assert Client(fake_api.url).qemu_binaries(compute_id=CID) == (200, {"version": "9.0.0"})


def test_port_nio_y_port_capture_aceptan_compute(fake_api):
    base = f"/v2/computes/{CID}/projects/{PID}/qemu/nodes/{NID}/adapters/1/ports/2"
    fake_api.route("PUT", f"{base}/nio", 200, {"type": "nio_udp"})
    fake_api.route("POST", f"{base}/start_capture", 201, {})
    c = Client(fake_api.url)

    assert c.port_nio(PID, NID, 1, 2, body={}, emulator="qemu",
                      compute_id=CID) == (200, {"type": "nio_udp"})
    assert c.port_capture(PID, NID, 1, 2, "start_capture", emulator="qemu",
                          compute_id=CID)[0] == 201
    assert fake_api.last("PUT", f"{base}/nio")
    assert fake_api.last("POST", f"{base}/start_capture")


# ───────────────────────── tools MCP ─────────────────────────
def test_tools_nuevas_expuestas():
    tools = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert {"gns3_project_file_list", "gns3_compute_endpoint"} <= tools


def test_mcp_project_file_list_filtra(fake_api, monkeypatch):
    monkeypatch.setattr(server, "_conf", lambda: {
        "url": fake_api.url, "user": "u", "password": "p"})
    fake_api.set_projects([{"project_id": PID, "name": "lab", "status": "opened"}])
    fake_api.route("GET", f"/v2/projects/{PID}", 200,
                   {"project_id": PID, "name": "lab", "status": "opened"})
    fake_api.route("GET", f"/v2/computes/local/projects/{PID}/files", 200, [
        {"path": "config.xml", "md5sum": "a"},
        {"path": "routers/r1/startup-config", "md5sum": "b"},
    ])

    res = server.gns3_project_file_list(project_id=PID, prefix="routers/")

    assert [f["path"] for f in res] == ["routers/r1/startup-config"]


def test_mcp_compute_endpoint_no_llama_a_la_url(fake_api, monkeypatch):
    monkeypatch.setattr(server, "_conf", lambda: {
        "url": fake_api.url, "user": "u", "password": "p"})
    url = "http://127.0.0.1:3081/v2/compute/qemu/binaries"
    fake_api.route("GET", f"/v2/computes/endpoint/{CID}/qemu/binaries", 200,
                   {"endpoint": url})

    res = server.gns3_compute_endpoint(CID, "qemu", "binaries")

    assert res["endpoint"] == url
    assert fake_api.last("GET", f"/v2/computes/endpoint/{CID}/qemu/binaries")
    assert not any(req["path"].startswith("/v2/compute/") for req in fake_api.requests)
