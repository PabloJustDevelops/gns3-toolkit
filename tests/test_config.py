"""Configuración de servidores: `local_auth`, `lab_conf`, `server_config`, `from_name`."""
import json

import pytest

import gns3core
from gns3core import Client, lab_conf, local_auth, server_config

CONF = {
    "servers": {
        "local": {"url": "http://127.0.0.1:3080/", "auth": "from-gns3-conf"},
        "clase": {"url": "http://192.168.71.250:80", "auth": None,
                  "matcher": "Pablo Rodriguez"},
    },
    "default_server": "local",
}


@pytest.fixture
def conf_files(tmp_path, monkeypatch):
    """Apunta las dos rutas de configuración a un directorio temporal."""
    gns3_conf = tmp_path / "gns3_server.conf"
    lab_conf_path = tmp_path / "config.json"
    monkeypatch.setattr(gns3core, "GNS3_CONF", gns3_conf)
    monkeypatch.setattr(gns3core, "LAB_CONF", lab_conf_path)
    return gns3_conf, lab_conf_path


# ─────────────────────────────── local_auth ───────────────────────────────
def test_local_auth_sin_conf_devuelve_none(conf_files):
    assert local_auth() is None


def test_local_auth_lee_usuario_y_password(conf_files):
    gns3_conf, _ = conf_files
    gns3_conf.write_text("user = pablo\npassword = secreto\n")
    assert local_auth() == ("pablo", "secreto")


def test_local_auth_sin_ambos_campos_devuelve_none(conf_files):
    gns3_conf, _ = conf_files
    gns3_conf.write_text("user = pablo\npassword_db = otra_cosa\n")
    assert local_auth() is None


# ──────────────────────────────── lab_conf ────────────────────────────────
def test_lab_conf_por_defecto_si_no_hay_fichero(conf_files):
    conf = lab_conf()
    assert conf["default_server"] == "local"
    assert set(conf["servers"]) == {"local", "clase"}


def test_lab_conf_lee_el_json_del_usuario(conf_files):
    _, lab_conf_path = conf_files
    lab_conf_path.write_text(json.dumps({"servers": {}, "default_server": "clase"}))
    assert lab_conf() == {"servers": {}, "default_server": "clase"}


def test_lab_conf_json_roto_devuelve_el_default(conf_files):
    _, lab_conf_path = conf_files
    lab_conf_path.write_text("{esto no es json")
    assert lab_conf()["default_server"] == "local"


# ────────────────────────────── server_config ──────────────────────────────
def test_server_config_normaliza_url_y_resuelve_credenciales(conf_files):
    gns3_conf, _ = conf_files
    gns3_conf.write_text("user = pablo\npassword = secreto\n")
    s = server_config("local", CONF)
    assert s["name"] == "local"
    assert s["url"] == "http://127.0.0.1:3080"        # sin barra final
    assert s["auth"] == ("pablo", "secreto")


def test_server_config_sin_auth_no_lee_el_conf(conf_files):
    gns3_conf, _ = conf_files
    gns3_conf.write_text("user = pablo\npassword = secreto\n")
    s = server_config("clase", CONF)
    assert s["auth"] is None
    assert s["matcher"] == "Pablo Rodriguez"


def test_server_config_de_nombre_desconocido_falla():
    with pytest.raises(SystemExit, match="'nope' no configurado"):
        server_config("nope", CONF)


def test_server_config_sin_conf_usa_lab_conf(conf_files):
    _, lab_conf_path = conf_files
    lab_conf_path.write_text(json.dumps(CONF))
    assert server_config("clase")["url"] == "http://192.168.71.250:80"


# ─────────────────────────────── from_name ───────────────────────────────
def test_from_name_copia_url_auth_y_matcher(conf_files):
    c = Client.from_name("clase", CONF)
    assert c.url == "http://192.168.71.250:80"
    assert c.auth is None
    assert c.matcher == "Pablo Rodriguez"
    assert c.name == "clase"
