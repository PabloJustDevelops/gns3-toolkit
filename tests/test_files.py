"""`node_file_write`/`node_file_read`: cuerpo crudo y `Content-Type: text/plain`."""
from gns3core import Client, node_file_read, node_file_write, node_summary

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


# ─────────────────────────────── node_file_read ───────────────────────────────
def test_node_file_read_devuelve_el_texto(fake_api):
    fake_api.route("GET", "/v2/projects/p1/nodes/n1/files/startup.vpc", 200, CONTENIDO)
    assert node_file_read(Client(fake_api.url), "p1", "n1", "startup.vpc") == CONTENIDO


def test_node_file_read_quita_la_barra_inicial(fake_api):
    fake_api.route("GET", "/v2/projects/p1/nodes/n1/files/etc/hosts", 200, "127.0.0.1\n")
    assert node_file_read(Client(fake_api.url), "p1", "n1", "/etc/hosts") == "127.0.0.1\n"


def test_node_file_read_devuelve_el_error_con_el_cuerpo_recortado(fake_api):
    fake_api.route("GET", "/v2/projects/p1/nodes/n1/files/x", 404, {"message": "no existe"})
    res = node_file_read(Client(fake_api.url), "p1", "n1", "x")

    assert res["error"] == "HTTP 404"
    assert b"no existe" in res["detail"]


# ─────────────────────────────── node_summary ───────────────────────────────
def test_node_summary_extrae_los_campos_utiles():
    nodo = {
        "name": "R1", "node_id": "n1", "node_type": "dynamips", "status": "started",
        "console": 5001, "console_type": "telnet",
        "ports": [{"name": "Gi0/0", "port_number": 0}, {"name": "Gi0/1"}],
        "extra": "se ignora",
    }
    assert node_summary(nodo) == {
        "name": "R1", "node_id": "n1", "type": "dynamips", "status": "started",
        "console": 5001, "console_type": "telnet", "ports": ["Gi0/0", "Gi0/1"],
    }


def test_node_summary_tolera_nodo_minimo():
    assert node_summary({}) == {
        "name": None, "node_id": None, "type": None, "status": None,
        "console": None, "console_type": None, "ports": [],
    }
