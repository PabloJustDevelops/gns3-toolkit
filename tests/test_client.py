"""`Client` contra un `http.server` local (API /v2 falsa)."""
import socket

import pytest

from gns3core import Client, match_nodes

P1 = "11111111-aaaa-bbbb-cccc-000000000001"
P2 = "22222222-aaaa-bbbb-cccc-000000000002"
P3 = "33333333-aaaa-bbbb-cccc-000000000003"


def _project(name, pid, status="closed"):
    return {"name": name, "project_id": pid, "status": status}


def _node(name, nid, **extra):
    base = {"name": name, "node_id": nid, "node_type": "vpcs", "status": "started"}
    base.update(extra)
    return base


# ────────────────────────────────── básico ──────────────────────────────────
def test_alive_contra_servidor_levantado(fake_api):
    c = Client(fake_api.url)
    assert c.alive() is True
    assert "/v2/version" in [r["path"] for r in fake_api.requests]


def test_alive_false_si_no_hay_servidor():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()                       # puerto cerrado: conexión rechazada
    assert Client(f"http://127.0.0.1:{port}").alive() is False


def test_projects_devuelve_la_lista(fake_api):
    fake_api.set_projects([_project("lab-prueba", P1, "opened")])
    assert Client(fake_api.url).projects() == [_project("lab-prueba", P1, "opened")]


def test_projects_propaga_el_error_http(fake_api):
    fake_api.route("GET", "/v2/projects", 500, {"message": "boom"})
    with pytest.raises(RuntimeError, match=r"\[500\]"):
        Client(fake_api.url).projects()


def test_nodes_pide_el_proyecto_correcto(fake_api):
    fake_api.set_projects([_project("lab-prueba", P1, "opened")])
    fake_api.set_nodes(P1, [_node("PC1", "n1"), _node("PC2", "n2")])
    nodes = Client(fake_api.url).nodes(P1)
    assert [n["name"] for n in nodes] == ["PC1", "PC2"]
    assert fake_api.last("GET", f"/v2/projects/{P1}/nodes")


# ──────────────────────────── resolve_project ────────────────────────────
def test_resolve_por_nombre_parcial(fake_api):
    fake_api.set_projects([
        _project("lab-prueba", P1, "opened"),
        _project("examen-dic", P2),
    ])
    assert Client(fake_api.url).resolve_project("prueba")["project_id"] == P1


def test_resolve_por_id(fake_api):
    fake_api.set_projects([
        _project("lab-prueba", P1, "opened"),
        _project("examen-dic", P2),
    ])
    assert Client(fake_api.url).resolve_project(P2[:8])["name"] == "examen-dic"
    assert Client(fake_api.url).resolve_project(P2)["project_id"] == P2


def test_resolve_error_si_dos_coinciden(fake_api):
    fake_api.set_projects([
        _project("lab-prueba", P1, "opened"),
        _project("lab-otro", P2),
    ])
    with pytest.raises(SystemExit, match="es ambiguo"):
        Client(fake_api.url).resolve_project("lab")


def test_resolve_sin_needle_usa_el_unico_abierto(fake_api):
    fake_api.set_projects([
        _project("cerrado", P1),
        _project("abierto", P2, "opened"),
        _project("otro-cerrado", P3),
    ])
    assert Client(fake_api.url).resolve_project(None)["project_id"] == P2


def test_resolve_error_si_hay_dos_abiertos(fake_api):
    fake_api.set_projects([
        _project("uno", P1, "opened"),
        _project("dos", P2, "opened"),
    ])
    with pytest.raises(SystemExit, match="hay varios abiertos"):
        Client(fake_api.url).resolve_project(None)


def test_resolve_usa_matcher_para_desempatar_abiertos(fake_api):
    fake_api.set_projects([
        _project("proyecto de Ana", P1, "opened"),
        _project("proyecto de Pablo Rodriguez", P2, "opened"),
    ])
    c = Client(fake_api.url, matcher="Pablo Rodriguez")
    assert c.resolve_project(None)["project_id"] == P2


@pytest.mark.parametrize("matcher", ["nadie", "proyecto"])
def test_resolve_con_matcher_no_ambigua_si_hay_cero_o_varios_hits(fake_api, matcher):
    fake_api.set_projects([
        _project("proyecto de Ana", P1, "opened"),
        _project("proyecto de Pablo Rodriguez", P2, "opened"),
    ])
    with pytest.raises(SystemExit, match="hay varios abiertos"):
        Client(fake_api.url, matcher=matcher).resolve_project(None)


def test_resolve_sin_abiertos_y_un_solo_proyecto(fake_api):
    fake_api.set_projects([_project("solo", P1)])
    assert Client(fake_api.url).resolve_project(None)["project_id"] == P1


def test_resolve_sin_abiertos_y_varios_proyectos_falla(fake_api):
    fake_api.set_projects([_project("uno", P1), _project("dos", P2)])
    with pytest.raises(SystemExit, match="ninguno abierto"):
        Client(fake_api.url).resolve_project(None)


def test_resolve_falla_si_el_servidor_no_tiene_proyectos(fake_api):
    fake_api.set_projects([])
    with pytest.raises(SystemExit, match="el servidor no tiene proyectos"):
        Client(fake_api.url, name="clase").resolve_project(None)


def test_resolve_falla_si_no_coincide_ninguno(fake_api):
    fake_api.set_projects([_project("uno", P1), _project("dos", P2)])
    with pytest.raises(SystemExit, match="ningún proyecto coincide con 'examen'"):
        Client(fake_api.url).resolve_project("examen")


# ──────────────────────────────── match_nodes ────────────────────────────────
NODES = [
    _node("R1", "id-r1"),
    _node("R2", "id-r2"),
    _node("R3", "id-r3"),
    _node("PC1", "id-pc1"),
]


def _names(pattern):
    return [n["name"] for n in match_nodes(NODES, pattern)]


def test_match_nodes_asterisco_devuelve_todos():
    assert _names("*") == ["R1", "R2", "R3", "PC1"]
    assert _names("all") == ["R1", "R2", "R3", "PC1"]


def test_match_nodes_prefijo():
    assert _names("R*") == ["R1", "R2", "R3"]


def test_match_nodes_globs_de_corchete():
    assert _names("R[12]") == ["R1", "R2"]


def test_match_nodes_lista_con_comas():
    assert _names("R1, R3") == ["R1", "R3"]


def test_match_nodes_lista_entre_corchetes():
    assert _names("[R1, PC1]") == ["R1", "PC1"]


def test_match_nodes_ignora_mayusculas():
    assert _names("r2") == ["R2"]


def test_match_nodes_por_node_id():
    assert _names("id-pc1") == ["PC1"]


def test_match_nodes_sin_coincidencias():
    assert _names("SW9") == []
    assert match_nodes(NODES, None) == []
