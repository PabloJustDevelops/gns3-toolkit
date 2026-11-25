"""Ramas que faltaban en ``pfsense.py``: XML raro, fallos de ``run()`` y guardado.

Sólo pruebas: cada caso ejercita el camino real de ``pfsense.py`` sin dobles que
salten la lógica (``run`` se sustituye donde el host es SSH y no hay servidor).
"""
from __future__ import annotations

import base64
import re
import subprocess

import pytest

import pfsense

PASSWORD = "clave-secreta-de-prueba"
IFCONFIG_OUTPUT = """em0: flags=8843<UP>
    inet 192.0.2.1 netmask 0xffffff00
em1: flags=8843<UP>
    inet 192.168.10.1 netmask 0xffffff00
"""


@pytest.fixture(autouse=True)
def limpia_entorno_pfsense(monkeypatch):
    for name in (
        "PFSENSE_HOST", "PFSENSE_USER", "PFSENSE_PASSWORD",
        "PFSENSE_PORT", "PFSENSE_TIMEOUT",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def client():
    return pfsense.PfSense(password=PASSWORD)


def _captura_guardado(monkeypatch, client, doc):
    escrituras = []

    def fake_put(document, backup=True):
        escrituras.append((document, backup))
        return {"ok": True, "backup": "/conf/config.xml.bak-prueba", "detail": "ok"}

    monkeypatch.setattr(client, "get_config", lambda: doc)
    monkeypatch.setattr(client, "put_config", fake_put)
    return escrituras


def _run_ok(monkeypatch, client):
    monkeypatch.setattr(client, "run", lambda cmd, timeout=None: {
        "ok": True, "output": IFCONFIG_OUTPUT, "error": None,
    })


def test_parse_config_acumula_tres_etiquetas_repetidas():
    doc = pfsense.parse_config(
        "<pfsense><lista><item>uno</item><item>dos</item><item>tres</item></lista></pfsense>"
    )

    assert doc["lista"]["item"] == ["uno", "dos", "tres"]


def test_run_timeout_sin_salida_ni_stderr_no_rompe_la_redaccion(monkeypatch, client):
    def fake_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ssh", timeout=1)

    monkeypatch.setattr(pfsense.subprocess, "run", fake_timeout)

    result = client.run("true", timeout=1)

    assert result == {"cmd": "true", "output": "", "ok": False,
                      "error": "timeout tras 1s"}


@pytest.mark.parametrize("timeout", [0, -1, "cero"])
def test_run_rechaza_timeout_no_positivo_ni_numerico(monkeypatch, client, timeout):
    monkeypatch.setattr(
        pfsense.subprocess, "run",
        lambda *args, **kwargs: pytest.fail("no debe lanzar sshpass"),
    )

    result = client.run("true", timeout=timeout)

    assert result == {"cmd": "true", "output": "", "ok": False,
                      "error": f"timeout no válido: {timeout}"}


@pytest.mark.parametrize(
    ("metodo", "args"),
    [
        ("set_ip", ("em1", "192.0.2.2", "24")),
        ("dhcp", ("em1", "192.168.10.100", "192.168.10.200")),
        ("rule", ()),
        ("nat", ()),
        ("enable_ssh", ()),
        ("assign", ({"wan": "em0"},)),
    ],
)
def test_cambios_propagan_error_al_leer_config(monkeypatch, client, metodo, args):
    _run_ok(monkeypatch, client)
    monkeypatch.setattr(client, "get_config", lambda: {"ok": False, "error": "config caído"})
    monkeypatch.setattr(client, "put_config", lambda *a, **k: pytest.fail("no debe escribir"))

    result = getattr(client, metodo)(*args)

    assert result == {"ok": False, "backup": None, "detail": "config caído"}


def test_put_config_trocea_payload_base64_grande(monkeypatch, client):
    comandos = []
    monkeypatch.setattr(client, "run", lambda cmd, timeout=None: (
        comandos.append(cmd) or {"ok": True, "output": "", "error": None}
    ))
    doc = {"system": {"hostname": "x" * 50000}}

    result = client.put_config(doc, backup=False)

    assert result["ok"] is True
    assert comandos[0] == "umask 077; : > /conf/config.xml.b64"
    assert comandos[-2].startswith(
        "umask 077; base64 -d /conf/config.xml.b64 > /conf/config.xml.tmp "
    )
    assert comandos[-2].endswith("rm -f /conf/config.xml.b64")
    assert comandos[-1] == "/etc/rc.reload_all"
    chunks = [
        re.search(r"printf '%s' '([^']+)' >> /conf/config.xml.b64", command).group(1)
        for command in comandos[1:-2]
    ]
    esperado = base64.b64encode(pfsense.render_config(doc).encode()).decode("ascii")
    assert len(esperado) > 60000
    assert "".join(chunks) == esperado
    assert [len(chunk) for chunk in chunks] == [60000, len(esperado) - 60000]


def test_interfaces_rechaza_seccion_no_diccionario(monkeypatch, client):
    _run_ok(monkeypatch, client)
    monkeypatch.setattr(client, "get_config", lambda: {"interfaces": ["lan", "wan"]})

    assert client.interfaces() == {
        "ok": False, "error": "la sección <interfaces> no es un diccionario",
    }


def test_interfaces_ignora_atributos_y_entradas_no_diccionario(monkeypatch, client):
    doc = {"interfaces": {
        "@attributes": {"modo": "sí"},
        "lan": {"if": "em1"},
        "opt9": "valor-no-diccionario",
    }}
    _run_ok(monkeypatch, client)
    monkeypatch.setattr(client, "get_config", lambda: doc)

    result = client.interfaces()

    assert list(result) == ["lan"]
    assert result["lan"] == {"if": "em1", "ip": "192.168.10.1",
                             "mask": "255.255.255.0", "dhcp": False}


def test_assign_crea_seccion_interfaces_ausente(monkeypatch, client):
    doc = {"system": {"hostname": "fw"}}
    _captura_guardado(monkeypatch, client, doc)
    _run_ok(monkeypatch, client)

    result = client.assign({"wan": "em0"})

    assert result["ok"] is True
    assert doc["interfaces"] == {"wan": {"if": "em0"}}


def test_set_ip_reemplaza_interfaz_logica_no_diccionario(monkeypatch, client):
    doc = {"interfaces": {"lan": "valor-no-diccionario"}}
    _captura_guardado(monkeypatch, client, doc)

    result = client.set_ip("lan", "192.168.10.2", "24")

    assert result["ok"] is True
    assert doc["interfaces"]["lan"] == {
        "ipaddr": "192.168.10.2", "subnet": "255.255.255.0",
    }


@pytest.mark.parametrize("dhcpd", [None, {"lan": "valor-no-diccionario"}])
def test_dhcp_crea_dhcpd_o_valor_no_diccionario(monkeypatch, client, dhcpd):
    doc = {"interfaces": {"lan": {"if": "em1"}}}
    if dhcpd is not None:
        doc["dhcpd"] = dhcpd
    _captura_guardado(monkeypatch, client, doc)

    result = client.dhcp("em1", "192.168.10.100", "192.168.10.200")

    assert result["ok"] is True
    assert doc["dhcpd"]["lan"]["range"] == {
        "from": "192.168.10.100", "to": "192.168.10.200",
    }


@pytest.mark.parametrize("nat", [None, "valor-no-diccionario"])
def test_nat_crea_seccion_si_falta_o_no_es_diccionario(monkeypatch, client, nat):
    doc = {"interfaces": {"wan": {"if": "em0"}}}
    if nat is not None:
        doc["nat"] = nat
    _captura_guardado(monkeypatch, client, doc)

    result = client.nat("wan")

    assert result["ok"] is True
    assert doc["nat"]["outbound"]["mode"] == "automatic"
    assert doc["nat"]["outbound"]["rule"][0]["interface"] == "wan"


@pytest.mark.parametrize("system", [None, "valor-no-diccionario"])
def test_enable_ssh_crea_seccion_system_si_falta(monkeypatch, client, system):
    doc = {}
    if system is not None:
        doc["system"] = system
    _captura_guardado(monkeypatch, client, doc)

    result = client.enable_ssh(2222)

    assert result["ok"] is True
    assert doc["system"]["ssh"] == {"enable": "on", "port": "2222"}


def test_enable_ssh_restaura_el_comando_de_recarga_previo(monkeypatch, client):
    vistos = []

    def fake_put(document, backup=True):
        vistos.append(client._reload_command)
        return {"ok": True, "backup": None, "detail": "ok"}

    monkeypatch.setattr(client, "get_config", lambda: {"system": {}})
    monkeypatch.setattr(client, "put_config", fake_put)
    client._reload_command = "/comando-previo"

    assert client.enable_ssh(2222)["ok"] is True
    assert vistos == ["/etc/rc.reload_all && /etc/sshd"]
    assert client._reload_command == "/comando-previo"


def test_enable_ssh_no_cambia_el_puerto_si_el_guardado_falla(monkeypatch, client):
    monkeypatch.setattr(client, "get_config", lambda: {"system": {}})
    monkeypatch.setattr(client, "put_config", lambda *a, **k: {
        "ok": False, "backup": None, "detail": "sin permiso",
    })

    result = client.enable_ssh(2222)

    assert result == {"ok": False, "backup": None, "detail": "sin permiso"}
    assert client.port == 22022
