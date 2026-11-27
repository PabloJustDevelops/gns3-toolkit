"""Contrato del reload de pfSense: timeout propio y verificación real."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import pfsense


PASSWORD = "clave-secreta-de-prueba"
DOC = {"system": {"hostname": "fw-nuevo"}}
OLD_DOC = {"system": {"hostname": "fw-viejo"}}


@pytest.fixture
def client():
    return pfsense.PfSense(password=PASSWORD)


def _response(ok=True, output="", error=None, **extra):
    return {"ok": ok, "output": output, "error": error, **extra}


def _put_con_reload(monkeypatch, client, reload_response, effective_doc=DOC):
    llamadas = []

    def fake_run(cmd, timeout=None):
        llamadas.append((cmd, timeout))
        if cmd == "/etc/rc.reload_all":
            return reload_response
        if cmd == "cat /conf/config.xml":
            return _response(output=pfsense.render_config(effective_doc))
        if cmd.startswith("umask 077;"):
            return _response()
        raise AssertionError(f"comando inesperado: {cmd}")

    monkeypatch.setattr(client, "run", fake_run)
    return llamadas


def test_reload_largo_usa_timeout_propio_y_lectura_sigue_en_20s(monkeypatch, client):
    llamadas = _put_con_reload(
        monkeypatch, client, _response(output="recargado tras 77s", returncode=0, stderr=""),
    )

    result = client.put_config(DOC, backup=False)

    assert result["ok"] is True
    assert result["detail"] == "recargado tras 77s"
    assert client.timeout == 20.0
    assert ("/etc/rc.reload_all", 180.0) in llamadas
    assert all(timeout is None for cmd, timeout in llamadas if cmd != "/etc/rc.reload_all")


def test_timeout_del_reload_verifica_config_antes_de_declarar_exito(monkeypatch, client):
    llamadas = _put_con_reload(
        monkeypatch, client, _response(ok=False, error="timeout tras 180s"),
    )

    result = client.put_config(DOC, backup=False)

    assert result["ok"] is True
    assert result["reload"] == "timeout"
    assert result["backup"] is None
    assert "timeout tras 180s" in result["detail"]
    assert ("cat /conf/config.xml", None) in llamadas


def test_timeout_del_reload_sin_el_cambio_no_es_exito(monkeypatch, client):
    _put_con_reload(
        monkeypatch, client, _response(ok=False, error="timeout tras 180s"),
        effective_doc=OLD_DOC,
    )

    result = client.put_config(DOC, backup=False)

    assert result["ok"] is False
    assert "timeout tras 180s" in result["detail"]


def test_timeout_del_reload_con_lectura_fallida_no_es_exito(monkeypatch, client):
    _put_con_reload(
        monkeypatch, client, _response(ok=False, error="timeout tras 180s", timeout=True),
    )
    monkeypatch.setattr(client, "get_config", lambda: {"ok": False, "error": "ssh caído"})

    result = client.put_config(DOC, backup=False)

    assert result["ok"] is False
    assert result["detail"] == "timeout tras 180s; verificación fallida: ssh caído"


def test_timeout_del_reload_usa_senal_explicita(monkeypatch, client):
    _put_con_reload(
        monkeypatch, client,
        _response(ok=False, error="reload interrumpido por límite", timeout=True),
    )

    result = client.put_config(DOC, backup=False)

    assert result["ok"] is True
    assert result["reload"] == "timeout"


def test_verificacion_acepta_campos_adicionales_del_reload(monkeypatch, client):
    effective_doc = {**DOC, "generado": {"valor": "durante el reload"}}
    _put_con_reload(
        monkeypatch, client, _response(ok=False, error="timeout tras 180s", timeout=True),
        effective_doc=effective_doc,
    )

    result = client.put_config(DOC, backup=False)

    assert result["ok"] is True
    assert result["reload"] == "timeout"


@pytest.mark.parametrize(
    ("expected", "actual", "contains"),
    [
        (["pass"], {"type": "pass"}, False),
        (["pass", "block"], ["reject", "pass", "log", "block", "reject"], True),
        (["pass", "block"], ["pass", "reject"], False),
        ([], [], True),
    ],
)
def test_config_contains_recorre_listas_y_rechaza_coincidencias_ausentes(
    expected, actual, contains,
):
    assert pfsense._config_contains(expected, actual) is contains


def test_detail_sin_ruido_openssh_conserva_otros_avisos(monkeypatch, client):
    def fake_subprocess(args, **kwargs):
        if args[-1] == "/etc/rc.reload_all":
            return SimpleNamespace(
                returncode=0,
                stdout="recargado\n",
                stderr=(
                    "** WARNING: connection is not using a post-quantum key exchange algorithm...\n"
                    "Warning: Permanently added '192.0.2.1' to the list of known hosts.\n"
                    "aviso que debe conservarse\n"
                ),
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pfsense.subprocess, "run", fake_subprocess)

    result = client.put_config(DOC, backup=False)

    assert result["ok"] is True
    assert "post-quantum" not in result["detail"]
    assert "known hosts" not in result["detail"]
    assert "recargado" in result["detail"]
    assert "aviso que debe conservarse" in result["detail"]


def test_timeout_de_lectura_por_defecto_no_cambia(monkeypatch, client):
    timeouts = []

    def fake_subprocess(args, **kwargs):
        timeouts.append(kwargs["timeout"])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pfsense.subprocess, "run", fake_subprocess)

    client.run("cat /conf/config.xml")

    assert timeouts == [20.0]
