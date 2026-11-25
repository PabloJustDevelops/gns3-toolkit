"""NIO, capturas por puerto, acciones masivas y consultas ampliadas."""
import json

import pytest

from gns3core import Client

PID = "p1"
NID = "abcdefgh-1234-5678-000000000001"
NODE_PATH = f"/v2/projects/{PID}/nodes/{NID}"


def _port_base(emulator, adapter=1, port=2):
    return (f"/v2/computes/local/projects/{PID}/{emulator}/nodes/{NID}"
            f"/adapters/{adapter}/ports/{port}")


@pytest.mark.parametrize(
    ("detail", "expected"),
    [
        ({"node_type": "vpcs"}, "vpcs"),
        ({"node_type": "docker"}, "docker"),
        ({}, "qemu"),
        ({"node_type": None}, "qemu"),
        (["no", "es", "dict"], "qemu"),
    ],
)
def test_emulator_for_usa_el_tipo_del_nodo_o_qemu(fake_api, detail, expected):
    fake_api.route("GET", NODE_PATH, 200, detail)
    assert Client(fake_api.url)._emulator_for(PID, NID) == expected
    assert fake_api.last("GET", NODE_PATH)


@pytest.mark.parametrize("emulator", [None, "docker"])
@pytest.mark.parametrize(
    ("operation", "http_method", "status", "response"),
    [
        ("delete", "DELETE", 204, b""),
        ("put", "PUT", 200, {"type": "udp"}),
        ("get", "GET", 200, {"type": "udp"}),
    ],
)
def test_port_nio_cubre_metodos_y_emulador(
        fake_api, emulator, operation, http_method, status, response):
    expected_emulator = emulator or "vpcs"
    path = f"{_port_base(expected_emulator)}/nio"
    if emulator is None:
        fake_api.route("GET", NODE_PATH, 200, {"node_type": "vpcs"})
    fake_api.route(http_method, path, status, response)
    c = Client(fake_api.url)

    if operation == "delete":
        result = c.port_nio(PID, NID, 1, 2, emulator=emulator, delete=True)
        assert result == (204, None)
    elif operation == "put":
        result = c.port_nio(PID, NID, 1, 2, body={"type": "udp"}, emulator=emulator)
        assert result == (200, {"type": "udp"})
    else:
        result = c.port_nio(PID, NID, 1, 2, emulator=emulator)
        assert result == (200, {"type": "udp"})

    req = fake_api.last(http_method, path)
    if operation == "put":
        assert req["body"] == b'{"type": "udp"}'
    else:
        assert req["body"] == b""
        assert "content-type" not in req["headers"]
    if emulator is None:
        assert fake_api.last("GET", NODE_PATH)
    else:
        assert not any(r["path"] == NODE_PATH for r in fake_api.requests)


def test_port_nio_con_body_vacio_sigue_siendo_put(fake_api):
    path = f"{_port_base('qemu')}/nio"
    fake_api.route("PUT", path, 200, {})
    assert Client(fake_api.url).port_nio(PID, NID, 1, 2, body={}, emulator="qemu") == (200, {})
    assert fake_api.last("PUT", path)["body"] == b"{}"


def test_port_nio_infiere_qemu_si_el_nodo_no_tiene_tipo(fake_api):
    path = f"{_port_base('qemu')}/nio"
    fake_api.route("GET", NODE_PATH, 200, {})
    fake_api.route("GET", path, 200, {"type": "nat"})
    assert Client(fake_api.url).port_nio(PID, NID, 1, 2) == (200, {"type": "nat"})
    assert fake_api.last("GET", path)


def test_port_nio_devuelve_tal_cual_el_error_del_compute(fake_api):
    path = f"{_port_base('qemu')}/nio"
    fake_api.route("PUT", path, 500, {"message": "ubridge no responde"})
    assert Client(fake_api.url).port_nio(
        PID, NID, 1, 2, body={"type": "udp"}, emulator="qemu") == (
            500, {"message": "ubridge no responde"})


@pytest.mark.parametrize(
    ("action", "file_name", "emulator", "expected_body"),
    [
        ("start_capture", None, None, {
            "capture_file_name": "port-abcdefgh-1-2.pcap",
            "data_link_type": "DLT_EN10MB",
        }),
        ("start_capture", "trafico.pcap", "docker", {
            "capture_file_name": "trafico.pcap",
            "data_link_type": "DLT_EN10MB",
        }),
        ("stop_capture", None, "qemu", {
            "capture_file_name": "port-abcdefgh-1-2.pcap",
        }),
    ],
)
def test_port_capture_start_y_stop_mandan_el_body_exacto(
        fake_api, action, file_name, emulator, expected_body):
    expected_emulator = emulator or "vpcs"
    path = f"{_port_base(expected_emulator)}/{action}"
    if emulator is None:
        fake_api.route("GET", NODE_PATH, 200, {"node_type": "vpcs"})
    fake_api.route("POST", path, 200, {"status": action})

    st, body = Client(fake_api.url).port_capture(
        PID, NID, 1, 2, action, file_name=file_name, emulator=emulator)

    assert st == 200 and body == {"status": action}
    assert json.loads(fake_api.last("POST", path)["body"]) == expected_body


def test_port_capture_pcap_devuelve_los_bytes_en_crudo(fake_api):
    path = f"{_port_base('vpcs')}/pcap"
    fake_api.route("GET", path, 200, b"PCAP-BYTES")
    assert Client(fake_api.url).port_capture(
        PID, NID, 1, 2, "pcap", emulator="vpcs") == (200, b"PCAP-BYTES")
    assert fake_api.last("GET", path)["body"] == b""


def test_port_capture_desconocida_falla_antes_de_hablar_con_la_api(fake_api):
    with pytest.raises(ValueError, match="acción de captura de puerto desconocida: dump"):
        Client(fake_api.url).port_capture(PID, NID, 1, 2, "dump")
    assert fake_api.requests == []


@pytest.mark.parametrize("action", ["start", "stop", "suspend", "reload"])
def test_nodes_action_manda_las_cuatro_acciones(fake_api, action):
    path = f"/v2/projects/{PID}/nodes/{action}"
    fake_api.route("POST", path, 200, {"status": action})
    assert Client(fake_api.url).nodes_action(PID, action) == (200, {"status": action})
    assert fake_api.last("POST", path)["body"] == b""


def test_nodes_action_desconocida_falla_antes_de_hablar_con_la_api(fake_api):
    with pytest.raises(ValueError, match="acción masiva desconocida: resume"):
        Client(fake_api.url).nodes_action(PID, "resume")
    assert fake_api.requests == []


def test_nodes_console_reset_manda_el_post(fake_api):
    path = f"/v2/projects/{PID}/nodes/console/reset"
    fake_api.route("POST", path, 200, {"status": "reset"})
    assert Client(fake_api.url).nodes_console_reset(PID) == (200, {"status": "reset"})
    assert fake_api.last("POST", path)["body"] == b""


@pytest.mark.parametrize("action", ["resume", "pause", "unpause"])
def test_node_action_acepta_las_acciones_nuevas(fake_api, action):
    path = f"/v2/projects/{PID}/nodes/{NID}/{action}"
    fake_api.route("POST", path, 200, {"status": action})
    assert Client(fake_api.url).node_action(PID, NID, action) == (200, {"status": action})
    assert fake_api.last("POST", path)["body"] == b""


@pytest.mark.parametrize("body", [None, {"image": "disco.qcow2"}])
def test_qemu_img_config_con_y_sin_body(fake_api, body):
    method = "PUT" if body is None else "POST"
    path = "/v2/computes/local/qemu/img"
    fake_api.route(method, path, 200, {"configured": True})
    assert Client(fake_api.url).qemu_img_config(body) == (200, {"configured": True})
    expected = b"{}" if body is None else b'{"image": "disco.qcow2"}'
    assert fake_api.last(method, path)["body"] == expected


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("qemu_img_binaries", "/v2/computes/local/qemu/img-binaries", ["qemu-img"]),
        ("virtualbox_vms", "/v2/computes/local/virtualbox/vms", [{"name": "VM-VB"}]),
        ("vmware_vms", "/v2/computes/local/vmware/vms", [{"name": "VM-VM"}]),
        ("v1_version", "/v1/version", {"version": "1.5.2"}),
    ],
)
def test_consultas_ampliadas_de_compute_y_version(fake_api, method, path, payload):
    fake_api.route("GET", path, 200, payload)
    assert getattr(Client(fake_api.url), method)() == (200, payload)
    assert fake_api.last("GET", path)


@pytest.mark.parametrize("body", [None, {"host_only": "vmnet1"}])
def test_vmware_vmnet_con_y_sin_body(fake_api, body):
    path = "/v2/computes/local/vmware/nodes/interfaces/vmnet"
    fake_api.route("POST", path, 200, {"configured": True})
    assert Client(fake_api.url).vmware_vmnet(body) == (200, {"configured": True})
    expected = b"{}" if body is None else b'{"host_only": "vmnet1"}'
    assert fake_api.last("POST", path)["body"] == expected


@pytest.mark.parametrize(
    ("url", "pid", "expected"),
    [
        ("http://127.0.0.1:3080/", None, "ws://127.0.0.1:3080/v2/notifications/ws"),
        ("http://127.0.0.1:3080/", PID,
         f"ws://127.0.0.1:3080/v2/projects/{PID}/notifications/ws"),
        ("https://gns3.example.test/", None, "wss://gns3.example.test/v2/notifications/ws"),
        ("https://gns3.example.test/", PID,
         f"wss://gns3.example.test/v2/projects/{PID}/notifications/ws"),
    ],
)
def test_notifications_ws_url_con_y_sin_proyecto(url, pid, expected):
    assert Client(url).notifications_ws_url(pid) == expected
