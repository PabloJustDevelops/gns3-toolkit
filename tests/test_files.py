"""`node_file_write`: cuerpo crudo y `Content-Type: text/plain`."""
from gns3core import Client, node_file_write

CONTENIDO = "ip dhcp\n\nset pcname PC1\n"


def test_node_file_write_manda_el_cuerpo_crudo(fake_api):
    fake_api.route("POST", "/v2/projects/p1/nodes/n1/files/startup.vpc", 201, b"")
    res = node_file_write(Client(fake_api.url), "p1", "n1", "startup.vpc", CONTENIDO)

    req = fake_api.last("POST", "/v2/projects/p1/nodes/n1/files/startup.vpc")
    assert req["headers"]["content-type"] == "text/plain"
    assert req["body"] == CONTENIDO.encode()
    assert not req["body"].startswith(b"{")
    assert b'"content"' not in req["body"]
    assert res == {"status": 201, "ok": True, "error": None}


def test_node_file_write_quita_la_barra_inicial(fake_api):
    fake_api.route("POST", "/v2/projects/p1/nodes/n1/files/startup.vpc", 200, b"")
    node_file_write(Client(fake_api.url), "p1", "n1", "/startup.vpc", "ip dhcp\n")
    assert fake_api.last("POST", "/v2/projects/p1/nodes/n1/files/startup.vpc")


def test_node_file_write_devuelve_el_error_de_la_api(fake_api):
    fake_api.route("POST", "/v2/projects/p1/nodes/n1/files/x", 400,
                   {"message": "no such node"})
    res = node_file_write(Client(fake_api.url), "p1", "n1", "x", "dato")

    assert res["ok"] is False
    assert res["status"] == 400
    assert res["error"] == {"message": "no such node"}
