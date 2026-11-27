"""Los fallos HTTP no deben convertirse en listas vacías en los puntos de decisión."""
from __future__ import annotations

import importlib.util
import json
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

import pytest

import gns3_mcp_server as server
from gns3core import Client

REPO = Path(__file__).resolve().parents[1]
CLI_PATH = REPO / "cli" / "gns3lab"
LOADER = SourceFileLoader("gns3lab_silent_errors", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)

PID = "11111111-aaaa-bbbb-cccc-000000000001"
LINKS_PATH = f"/v2/projects/{PID}/links"
SNAPSHOTS_PATH = f"/v2/projects/{PID}/snapshots"
DRAWINGS_PATH = f"/v2/projects/{PID}/drawings"
QEMU_IMAGES_PATH = "/v2/computes/local/qemu/images"

FAMILIES = [
    ("links", "links", (PID,), LINKS_PATH),
    ("qemu_images", "qemu_images", (), QEMU_IMAGES_PATH),
    ("computes", "computes", (), "/v2/computes"),
    ("symbols", "symbols", (), "/v2/symbols"),
    ("appliances", "appliances", (), "/v2/appliances"),
    ("images", "images", (), QEMU_IMAGES_PATH),
    ("snapshots", "snapshots", (PID,), SNAPSHOTS_PATH),
    ("drawings", "drawings", (PID,), DRAWINGS_PATH),
]


@pytest.fixture
def silent_api(fake_api, monkeypatch):
    project = {"project_id": PID, "name": "lab-prueba", "status": "opened"}
    nodes = [
        {"node_id": "nodo-pc1", "name": "PC1", "node_type": "vpcs",
         "ports": [{"adapter_number": 0, "port_number": 0}]},
        {"node_id": "nodo-pc2", "name": "PC2", "node_type": "vpcs",
         "ports": [{"adapter_number": 0, "port_number": 0}]},
    ]
    fake_api.set_projects([project])
    fake_api.route("GET", f"/v2/projects/{PID}", 200, project)
    fake_api.set_nodes(PID, nodes)
    conf = {"url": fake_api.url, "user": "u", "password": "p",
            "host": "127.0.0.1", "port": "3080"}
    monkeypatch.setattr(server, "_conf", lambda: conf)
    return fake_api, conf


def _requests(api, path):
    return [req for req in api.requests if req["method"] == "GET" and req["path"] == path]


def _cli_conf(conf):
    return {"servers": {"prueba": {"url": conf["url"], "auth": None}},
            "default_server": "prueba"}


@pytest.mark.parametrize("family,method,args,path", FAMILIES)
def test_variante_estricta_propaga_http_500_por_familia(
    fake_api, family, method, args, path
):
    fake_api.route("GET", path, 500, {"message": f"fallo {family}"})
    client = Client(fake_api.url)

    with pytest.raises(RuntimeError) as excinfo:
        client.json_list_or_die(path, family)

    texto = str(excinfo.value)
    assert texto.startswith(f"{family}: [500]")
    assert f"fallo {family}" in texto
    assert "no encontrado" not in texto.lower()


@pytest.mark.parametrize("family,method,args,path", FAMILIES)
def test_metodos_por_defecto_conservan_lista_vacia_ante_http_500(
    fake_api, family, method, args, path
):
    fake_api.route("GET", path, 500, {"message": f"fallo {family}"})
    assert getattr(Client(fake_api.url), method)(*args) == []


def test_variante_estricta_devuelve_una_lista_valida(fake_api):
    fake_api.route("GET", "/v2/symbols", 200, [{"symbol_id": "s1"}])
    assert Client(fake_api.url).json_list_or_die("/v2/symbols", "símbolos") == [
        {"symbol_id": "s1"}
    ]


def test_variante_estricta_rechaza_un_cuerpo_que_no_es_lista(fake_api):
    fake_api.route("GET", "/v2/symbols", 200, {"message": "forma inválida"})
    with pytest.raises(RuntimeError) as excinfo:
        Client(fake_api.url).json_list_or_die("/v2/symbols", "símbolos")
    assert "símbolos: [200]" in str(excinfo.value)
    assert "forma inválida" in str(excinfo.value)


@pytest.mark.parametrize(
    "tool,kwargs,path",
    [
        ("gns3_links", {"action": "list", "project_name": "lab-prueba"}, LINKS_PATH),
        ("gns3_drawings", {"action": "list", "project_name": "lab-prueba"}, DRAWINGS_PATH),
        ("gns3_snapshots", {"action": "list", "project_name": "lab-prueba"}, SNAPSHOTS_PATH),
        ("gns3_images", {}, QEMU_IMAGES_PATH),
        ("gns3_symbols", {}, "/v2/symbols"),
        ("gns3_appliances", {}, "/v2/appliances"),
        ("gns3_compute", {"action": "list"}, "/v2/computes"),
    ],
)
def test_listados_mcp_no_silencian_http_500_ni_reintentan_la_lectura(
    silent_api, tool, kwargs, path
):
    api, _ = silent_api
    api.route("GET", path, 500, {"message": "boom"})

    result = getattr(server, tool)(**kwargs)

    assert isinstance(result, dict), result
    assert "[500]" in result.get("error", "")
    assert "boom" in json.dumps(result, ensure_ascii=False, default=str)
    assert len(_requests(api, path)) == 1


def test_status_mcp_distingue_computes_no_leidos_de_lista_vacia(silent_api):
    api, _ = silent_api
    api.route("GET", "/v2/computes", 500, {"message": "boom computes"})
    api.route("GET", "/v1/version", 200, {"version": "2.2.61"})

    result = server.gns3_status()

    assert result["computes"] == []
    assert "[500]" in result["error"]
    assert "boom computes" in result["error"]


@pytest.mark.parametrize("action", ["list", "rm", "edit", "filters"])
def test_cmd_link_no_confunde_http_500_con_ningun_enlace(silent_api, action):
    api, conf = silent_api
    api.route("GET", LINKS_PATH, 500, {"message": "boom enlaces"})
    args = SimpleNamespace(
        server="prueba", project=None, action=action,
        nodes=[] if action == "list" else ["link-1"], set=[],
    )

    with pytest.raises(RuntimeError) as excinfo:
        cli.cmd_link(args, _cli_conf(conf))

    assert "[500]" in str(excinfo.value)
    assert "boom enlaces" in str(excinfo.value)
    assert "no encontrado" not in str(excinfo.value).lower()
    assert len(_requests(api, LINKS_PATH)) == 1


def test_examen_informe_no_escribe_cero_enlaces_si_la_api_falla(
    silent_api, tmp_path
):
    api, conf = silent_api
    api.route("GET", LINKS_PATH, 500, {"message": "boom enlaces"})
    dest = tmp_path / "informe.md"
    args = SimpleNamespace(
        action="informe", server="prueba", name="lab-prueba",
        dest=str(dest), json=True, global_json=False,
    )

    with pytest.raises(RuntimeError) as excinfo:
        cli.cmd_examen(args, _cli_conf(conf))

    assert "[500]" in str(excinfo.value)
    assert not dest.exists()


def test_examen_setup_no_confunde_http_500_imagenes_con_ausencia_de_disco(
    silent_api,
):
    api, _ = silent_api
    api.route("GET", QEMU_IMAGES_PATH, 500, {"message": "boom imágenes"})

    with pytest.raises(RuntimeError) as excinfo:
        cli._examen_disk(Client(api.url))

    assert "[500]" in str(excinfo.value)
    assert "boom imágenes" in str(excinfo.value)


@pytest.mark.parametrize(
    "action,extra",
    [
        ("add", {"node_a": "PC1", "node_b": "PC2"}),
        ("delete", {"link_id": "link-1"}),
    ],
)
def test_link_edit_no_escribe_si_no_pudo_leer_los_enlaces(
    silent_api, action, extra
):
    api, _ = silent_api
    api.route("GET", LINKS_PATH, 500, {"message": "boom enlaces"})

    result = server.gns3_link_edit(
        action=action, project_name="lab-prueba", **extra
    )

    assert "[500]" in result.get("error", "")
    assert "no encontrado" not in json.dumps(result, ensure_ascii=False).lower()
    assert not any(req["method"] in {"POST", "PUT", "DELETE"} for req in api.requests)
    assert len(_requests(api, LINKS_PATH)) == 1


@pytest.mark.parametrize("action", ["restore", "delete"])
def test_snapshots_por_nombre_no_escriben_si_la_lista_falla(silent_api, action):
    api, _ = silent_api
    api.route("GET", SNAPSHOTS_PATH, 500, {"message": "boom snapshots"})

    result = server.gns3_snapshots(
        action=action, project_name="lab-prueba", name="snap-1"
    )

    assert "[500]" in result.get("error", "")
    assert "no encontrado" not in json.dumps(result, ensure_ascii=False).lower()
    assert not any(req["method"] in {"POST", "PUT", "DELETE"} for req in api.requests)
    assert len(_requests(api, SNAPSHOTS_PATH)) == 1
