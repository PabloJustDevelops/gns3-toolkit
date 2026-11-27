"""Contrato de pfSense nativo con SSH y config.xml doblados, sin host real."""
from __future__ import annotations

import base64
import re
import subprocess
import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest

import pfsense


def test_contrato_api_publica_de_pfsense_presente():
    for nombre in (
        "PfSense", "PfSenseError", "parse_config", "render_config", "detect_ifnames",
    ):
        assert hasattr(pfsense, nombre), f"falta pfsense.{nombre}"


PASSWORD = "clave-secreta-de-prueba"
CONFIG_XML = """<pfsense>
  <system><hostname>fw</hostname><ssh><enable>on</enable><port>22022</port></ssh></system>
  <interfaces>
    <wan><if>em0</if><ipaddr>192.0.2.1</ipaddr><subnet>24</subnet></wan>
    <lan><if>em1</if><ipaddr>192.168.10.1</ipaddr><subnet>24</subnet></lan>
  </interfaces>
  <dhcpd><lan><enable></enable><range><from>192.168.10.100</from><to>192.168.10.200</to></range></lan></dhcpd>
  <filter>
    <rule><type>pass</type><interface>lan</interface></rule>
    <rule><type>reject</type><interface>lan</interface></rule>
  </filter>
  <nat><outbound><mode>automatic</mode><rule><type>reject</type><interface>wan</interface></rule></outbound></nat>
  <desconocido modo="sí"><item id="a">uno</item><item id="b">dos</item></desconocido>
</pfsense>"""
IFCONFIG_OUTPUT = """em0: flags=8843<UP>
    inet 192.0.2.1 netmask 0xffffff00
em1: flags=8843<UP>
    inet 192.168.10.1 netmask 0xffffff00
em2: flags=8843<UP>
    inet 192.168.20.1 netmask 0xffffff00
em3: flags=8843<UP>
    inet 192.0.2.3 netmask 0xno-valida
vtnet0: flags=8843<UP>
    inet 10.0.0.1 netmask 255.255.255.0
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


def _doc():
    return pfsense.parse_config(CONFIG_XML)


def _captura_guardado(monkeypatch, client, doc):
    escrituras = []

    def fake_put(document, backup=True):
        escrituras.append((document, backup))
        return {"ok": True, "backup": "/conf/config.xml.bak-prueba", "detail": "ok"}

    monkeypatch.setattr(client, "get_config", lambda: doc)
    monkeypatch.setattr(client, "put_config", fake_put)
    return escrituras


def test_parse_render_idempotentes_conservan_secciones_y_atributos():
    doc = pfsense.parse_config(CONFIG_XML)

    assert {"system", "interfaces", "filter", "nat", "desconocido"} <= doc.keys()
    assert doc["desconocido"]["@attributes"] == {"modo": "sí"}
    assert [item["@attributes"]["id"] for item in doc["desconocido"]["item"]] == ["a", "b"]

    rendered = pfsense.render_config(doc)
    root = ET.fromstring(rendered)
    assert root.tag == "pfsense"
    assert root.findtext("system/hostname") == "fw"
    assert root.findtext("interfaces/wan/if") == "em0"
    assert root.findtext("interfaces/lan/if") == "em1"
    assert len(root.findall("filter/rule")) == 2
    assert root.find("nat/outbound") is not None
    assert root.findtext("desconocido/item") == "uno"
    assert pfsense.parse_config(rendered) == doc
    assert pfsense.render_config(pfsense.parse_config(rendered)) == rendered


@pytest.mark.parametrize("xml", ["<pfsense>", "<otro/>", None])
def test_parse_config_rechaza_xml_invalido_o_raiz_ajena(xml):
    with pytest.raises(pfsense.PfSenseError):
        pfsense.parse_config(xml)


def test_render_config_exige_diccionario():
    with pytest.raises(pfsense.PfSenseError):
        pfsense.render_config([])


@pytest.mark.parametrize(
    ("adapter", "expected"),
    [
        ("e1000", {"wan": "em0", "lan": "em1", "adapter_type": "e1000"}),
        ("e1000e", {"wan": "em0", "lan": "em1", "adapter_type": "e1000e"}),
        ("virtio-net-pci", {"wan": "vtnet0", "lan": "vtnet1", "adapter_type": "virtio-net-pci"}),
    ],
)
def test_detect_ifnames_para_adaptadores_soportados(adapter, expected):
    assert pfsense.detect_ifnames({"properties": {"adapter_type": adapter}}) == expected


@pytest.mark.parametrize("node", [None, {}, {"properties": {}}, {"properties": {"adapter_type": "rtl8139"}}])
def test_detect_ifnames_rechaza_adaptador_desconocido(node):
    with pytest.raises(pfsense.PfSenseError):
        pfsense.detect_ifnames(node)


def test_from_env_lee_los_cuatro_nombres(monkeypatch):
    monkeypatch.setenv("PFSENSE_HOST", "192.0.2.10")
    monkeypatch.setenv("PFSENSE_USER", "operador")
    monkeypatch.setenv("PFSENSE_PASSWORD", PASSWORD)
    monkeypatch.setenv("PFSENSE_PORT", "2222")

    client = pfsense.PfSense.from_env()

    assert (client.host, client.user, client.password) == ("192.0.2.10", "operador", PASSWORD)
    assert (client.port, client.timeout) == (2222, 20.0)


def test_from_env_aplica_defaults_sin_inventar_credenciales(monkeypatch):
    monkeypatch.setenv("PFSENSE_PASSWORD", PASSWORD)

    client = pfsense.PfSense.from_env()

    assert (client.host, client.user, client.port, client.timeout) == (
        "192.168.1.1", "admin", 22022, 20.0,
    )


def test_from_env_nombra_la_variable_que_falta(monkeypatch):
    with pytest.raises(pfsense.PfSenseError, match="PFSENSE_PASSWORD"):
        pfsense.PfSense.from_env()


def test_from_env_rechaza_puerto_no_numerico(monkeypatch):
    monkeypatch.setenv("PFSENSE_PASSWORD", PASSWORD)
    monkeypatch.setenv("PFSENSE_PORT", "veintidos")

    with pytest.raises(pfsense.PfSenseError, match="PFSENSE_PORT"):
        pfsense.PfSense.from_env()


@pytest.mark.parametrize("returncode", [0, 7])
def test_run_enmascara_password_en_comando_stdout_y_stderr(monkeypatch, client, returncode):
    llamadas = []

    def fake_run(args, **kwargs):
        llamadas.append((args, kwargs))
        return SimpleNamespace(
            returncode=returncode,
            stdout=f"salida {PASSWORD}\n",
            stderr=f"error {PASSWORD}\n",
        )

    monkeypatch.setattr(pfsense.subprocess, "run", fake_run)
    result = client.run(f"echo {PASSWORD}", timeout=3)

    assert result["ok"] is (returncode == 0)
    assert result["cmd"] == "echo ***"
    assert PASSWORD not in repr(result)
    assert "***" in result["output"]
    if returncode:
        assert "***" in result["error"]
    args, kwargs = llamadas[0]
    assert args[:3] == ["sshpass", "-e", "ssh"]
    assert PASSWORD not in args, "la contraseña no puede viajar en argv (visible con ps)"
    assert kwargs["env"]["SSHPASS"] == PASSWORD
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["timeout"] == 3.0


def test_run_sin_password_o_comando_vacio_no_ejecuta_ssh(monkeypatch, client):
    def fake_run(*args, **kwargs):
        raise AssertionError("no debe lanzar sshpass")

    monkeypatch.setattr(pfsense.subprocess, "run", fake_run)
    assert pfsense.PfSense().run("true")["ok"] is False
    assert client.run("  ")["error"] == "comando vacío"


def test_run_enmascara_timeout_y_error_del_sistema(monkeypatch, client):
    def fake_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd="ssh", timeout=1,
            output=f"salida {PASSWORD}".encode(),
            stderr=f"error {PASSWORD}".encode(),
        )

    monkeypatch.setattr(pfsense.subprocess, "run", fake_timeout)
    timeout = client.run("true", timeout=1)
    assert timeout["ok"] is False
    assert PASSWORD not in repr(timeout)
    assert "timeout" in timeout["error"]

    def fake_oserror(*args, **kwargs):
        raise OSError(f"sshpass indisponible: {PASSWORD}")

    monkeypatch.setattr(pfsense.subprocess, "run", fake_oserror)
    error = client.run("true")
    assert error["ok"] is False
    assert PASSWORD not in repr(error)


def test_status_recoge_version_interfaces_reglas_y_rutas(monkeypatch, client):
    respuestas = {
        "cat /etc/version": {"ok": True, "output": "2.7", "error": None},
        "ifconfig": {"ok": True, "output": IFCONFIG_OUTPUT, "error": None},
        "pfctl -sr": {"ok": True, "output": "pass in all", "error": None},
        "netstat -rn": {"ok": True, "output": "default 192.0.2.254", "error": None},
    }
    monkeypatch.setattr(client, "run", lambda cmd, timeout=None: respuestas[cmd])

    result = client.status()

    assert result["ok"] is True
    assert result["version"] == "2.7"
    assert result["interfaces"] == IFCONFIG_OUTPUT
    assert result["rules"] == "pass in all"
    assert result["routes"] == "default 192.0.2.254"


def test_status_aisla_errores_y_los_acumula(monkeypatch, client):
    def fake_run(cmd, timeout=None):
        ok = cmd != "pfctl -sr"
        return {"ok": ok, "output": "ok" if ok else "", "error": None if ok else "pfctl caído"}

    monkeypatch.setattr(client, "run", fake_run)
    result = client.status()

    assert result["ok"] is False
    assert result["rules"] == "pfctl caído"
    assert result["errors"] == ["pfctl -sr: pfctl caído"]


def test_get_config_conserva_el_xml_crudo_y_run_redacta_la_salida_publica(monkeypatch, client):
    valor = f"antes-{PASSWORD}-despues"
    xml = f"<pfsense><system/><desconocido><valor>{valor}</valor></desconocido></pfsense>"
    monkeypatch.setattr(pfsense.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=0, stdout=xml, stderr="",
    ))

    doc = client.get_config()
    resultado_publico = client.run("cat /conf/config.xml")

    assert doc["desconocido"]["valor"] == valor
    assert resultado_publico["output"] == xml.replace(PASSWORD, "***")
    assert PASSWORD not in repr(resultado_publico)


def test_get_config_parsea_xml_y_propaga_errores(monkeypatch, client):
    monkeypatch.setattr(client, "_run", lambda cmd, timeout=None: {
        "ok": True, "output": CONFIG_XML, "error": None,
    })
    assert client.get_config()["system"]["hostname"] == "fw"

    monkeypatch.setattr(client, "_run", lambda cmd, timeout=None: {
        "ok": False, "output": "", "error": "sin config.xml",
    })
    assert client.get_config() == {"ok": False, "error": "sin config.xml"}

    monkeypatch.setattr(client, "_run", lambda cmd, timeout=None: {
        "ok": True, "output": "<pfsense>", "error": None,
    })
    assert client.get_config()["ok"] is False

    monkeypatch.setattr(client, "_run", lambda cmd, timeout=None: {
        "ok": False, "output": "", "error": f"error con {PASSWORD}",
    })
    error = client.get_config()
    assert error["error"] == "error con ***"
    assert PASSWORD not in repr(error)


def test_put_config_hace_backup_escribe_xml_y_recarga(monkeypatch, client):
    comandos = []

    def fake_run(cmd, timeout=None):
        comandos.append(cmd)
        return {"ok": True, "output": "recargado" if cmd == "/etc/rc.reload_all" else "", "error": None}

    monkeypatch.setattr(client, "run", fake_run)
    doc = {"system": {"hostname": "fw"}}
    result = client.put_config(doc)

    assert result["ok"] is True
    assert result["backup"].startswith("/conf/config.xml.bak-")
    assert result["detail"] == "recargado"
    assert len(comandos) == 3
    assert comandos[0].startswith("cp -p /conf/config.xml ")
    assert comandos[-1] == "/etc/rc.reload_all"
    encoded = re.search(r"printf '%s' '([^']+)'", comandos[1]).group(1)
    assert base64.b64decode(encoded).decode() == pfsense.render_config(doc)


def test_put_config_sin_backup_omite_la_copia(monkeypatch, client):
    comandos = []
    monkeypatch.setattr(client, "run", lambda cmd, timeout=None: (
        comandos.append(cmd) or {"ok": True, "output": "", "error": None}
    ))

    result = client.put_config({"system": {}}, backup=False)

    assert result["ok"] is True
    assert result["backup"] is None
    assert len(comandos) == 2
    assert not any(cmd.startswith("cp ") for cmd in comandos)


@pytest.mark.parametrize(
    ("paso_fallido", "llamadas_esperadas"),
    [("cp ", 1), ("printf ", 2), ("/etc/rc.reload_all", 3)],
)
def test_put_config_detiene_escritura_si_falla_backup_o_recarga(
    monkeypatch, client, paso_fallido, llamadas_esperadas,
):
    comandos = []

    def fake_run(cmd, timeout=None):
        comandos.append(cmd)
        ok = paso_fallido not in cmd
        return {"ok": ok, "output": "", "error": None if ok else f"fallo {paso_fallido.strip()}"}

    monkeypatch.setattr(client, "run", fake_run)
    result = client.put_config({"system": {}})

    assert result["ok"] is False
    assert len(comandos) == llamadas_esperadas
    assert f"fallo {paso_fallido.strip()}" in result["detail"]
    assert (result["backup"] is None) is (paso_fallido == "cp ")


def test_put_config_no_ejecuta_comandos_si_el_documento_es_invalido(monkeypatch, client):
    monkeypatch.setattr(client, "run", lambda *args, **kwargs: pytest.fail("no debe ejecutar SSH"))
    assert client.put_config([])["ok"] is False


def test_interfaces_combina_ifconfig_y_config_xml(monkeypatch, client):
    doc = _doc()
    doc["interfaces"]["opt1"] = {"if": "em2", "ipaddr": "dhcp", "subnet": "24"}
    doc["interfaces"]["lan"]["subnet"] = "mascara-mala"
    monkeypatch.setattr(client, "run", lambda cmd, timeout=None: {
        "ok": True, "output": IFCONFIG_OUTPUT, "error": None,
    })
    monkeypatch.setattr(client, "get_config", lambda: doc)

    result = client.interfaces()

    assert result["wan"] == {"if": "em0", "ip": "192.0.2.1", "mask": "255.255.255.0", "dhcp": False}
    assert result["lan"]["ip"] == "192.168.10.1"
    assert result["opt1"] == {"if": "em2", "ip": "192.168.20.1", "mask": "255.255.255.0", "dhcp": True}


def test_interfaces_propaga_fallo_de_ifconfig_o_config(monkeypatch, client):
    monkeypatch.setattr(client, "run", lambda cmd, timeout=None: {
        "ok": False, "output": "", "error": "ifconfig caído",
    })
    assert client.interfaces() == {"ok": False, "error": "ifconfig caído"}

    monkeypatch.setattr(client, "run", lambda cmd, timeout=None: {
        "ok": True, "output": IFCONFIG_OUTPUT, "error": None,
    })
    monkeypatch.setattr(client, "get_config", lambda: {"ok": False, "error": "config caído"})
    assert client.interfaces() == {"ok": False, "error": "config caído"}


def test_assign_interfaz_inexistente_nombra_las_disponibles(monkeypatch, client):
    monkeypatch.setattr(client, "run", lambda cmd, timeout=None: {
        "ok": True, "output": IFCONFIG_OUTPUT, "error": None,
    })

    result = client.assign({"wan": "em9", "lan": "em1"})

    assert result["ok"] is False
    assert "em9" in result["error"]
    for name in ("em0", "em1", "em2", "em3", "vtnet0"):
        assert name in result["error"]
    assert result["available"] == ["em0", "em1", "em2", "em3", "vtnet0"]


@pytest.mark.parametrize(
    ("mapping", "mensaje"),
    [
        ({}, "mapping"),
        ({"dmz": "em0"}, "rol"),
        ({"wan": "em0", "lan": "em0"}, "ya está asignada"),
    ],
)
def test_assign_rechaza_mapping_invalido_sin_escribir(monkeypatch, client, mapping, mensaje):
    monkeypatch.setattr(client, "run", lambda cmd, timeout=None: {
        "ok": True, "output": IFCONFIG_OUTPUT, "error": None,
    })
    monkeypatch.setattr(client, "put_config", lambda *args, **kwargs: pytest.fail("no debe escribir"))

    result = client.assign(mapping)

    assert result["ok"] is False
    assert mensaje in result["error"]


def test_assign_propaga_fallo_de_ifconfig(monkeypatch, client):
    monkeypatch.setattr(client, "run", lambda cmd, timeout=None: {
        "ok": False, "output": "", "error": "ifconfig caído",
    })
    assert client.assign({"wan": "em0"}) == {"ok": False, "error": "ifconfig caído"}


def test_assign_rechaza_interfaz_usada_por_un_rol_omitido(monkeypatch, client):
    doc = _doc()
    doc["interfaces"]["opt1"] = {"if": "em2"}
    escrituras = []
    monkeypatch.setattr(client, "run", lambda cmd, timeout=None: {
        "ok": True, "output": IFCONFIG_OUTPUT, "error": None,
    })
    monkeypatch.setattr(client, "get_config", lambda: doc)
    monkeypatch.setattr(client, "put_config", lambda documento: (
        escrituras.append(documento) or {"ok": True}
    ))

    result = client.assign({"wan": "em2"})

    assert result["ok"] is False
    assert "em2" in result["detail"]
    assert "opt1" in result["detail"]
    assert escrituras == []


def test_assign_actualiza_roles_y_elimina_opt1(monkeypatch, client):
    doc = _doc()
    doc["interfaces"]["opt1"] = {"if": "em2"}
    doc["interfaces"]["opt2"] = "valor-no-diccionario"
    escrituras = _captura_guardado(monkeypatch, client, doc)
    monkeypatch.setattr(client, "run", lambda cmd, timeout=None: {
        "ok": True, "output": IFCONFIG_OUTPUT, "error": None,
    })

    result = client.assign({"wan": "em0", "lan": "em1", "opt1": None, "opt2": "em2"})

    assert result["ok"] is True
    assert "opt1" not in doc["interfaces"]
    assert doc["interfaces"]["opt2"]["if"] == "em2"
    assert escrituras == [(doc, True)]


def test_set_ip_normaliza_mascara_y_crea_gateway_nombrado(monkeypatch, client):
    doc = _doc()
    _captura_guardado(monkeypatch, client, doc)

    result = client.set_ip("em0", "192.0.2.2", "24", "192.0.2.254")

    assert result["ok"] is True
    assert doc["interfaces"]["wan"]["ipaddr"] == "192.0.2.2"
    assert doc["interfaces"]["wan"]["subnet"] == "24"
    assert doc["interfaces"]["wan"]["gateway"] == "WANGW"
    assert doc["gateways"]["defaultgw4"] == "WANGW"
    assert doc["gateways"]["gateway_item"] == {
        "interface": "wan", "gateway": "192.0.2.254", "ipprotocol": "inet",
        "name": "WANGW", "descr": "", "weight": "", "gw_down_kill_states": "",
    }
    root = ET.fromstring(pfsense.render_config(doc))
    assert root.findtext("interfaces/wan/gateway") == "WANGW"
    assert root.findtext("gateways/gateway_item/gateway") == "192.0.2.254"
    assert pfsense.parse_config(pfsense.render_config(doc))["gateways"] == doc["gateways"]


def test_set_ip_conserva_gateway_existente_con_otro_nombre(monkeypatch, client):
    doc = _doc()
    existente = {"name": "UPSTREAM", "interface": "wan", "gateway": "192.0.2.254"}
    doc["gateways"] = {"defaultgw4": "UPSTREAM", "gateway_item": existente}
    _captura_guardado(monkeypatch, client, doc)

    assert client.set_ip("em0", "192.0.2.2", "24", "192.0.2.254")["ok"] is True

    assert doc["gateways"]["gateway_item"][0] == existente
    assert [item["name"] for item in doc["gateways"]["gateway_item"]] == ["UPSTREAM", "WANGW"]


def test_set_ip_en_lan_no_mueve_la_ruta_por_defecto(monkeypatch, client):
    doc = _doc()
    doc["gateways"] = {"defaultgw4": "WANGW"}
    _captura_guardado(monkeypatch, client, doc)

    assert client.set_ip("em1", "192.168.10.2", "24", "192.168.10.254")["ok"] is True

    assert doc["interfaces"]["lan"]["gateway"] == "LANGW"
    assert doc["gateways"]["defaultgw4"] == "WANGW"


@pytest.mark.parametrize("mask", ["24", "255.255.255.0"])
def test_set_ip_guarda_subnet_como_cidr(monkeypatch, client, mask):
    doc = _doc()
    _captura_guardado(monkeypatch, client, doc)

    result = client.set_ip("em1", "192.168.10.2", mask)

    assert result["ok"] is True
    assert doc["interfaces"]["lan"]["subnet"] == "24"
    assert ET.fromstring(pfsense.render_config(doc)).findtext("interfaces/lan/subnet") == "24"


@pytest.mark.parametrize(
    ("ip", "mask", "gateway"),
    [("no-es-ip", "24", None), ("192.0.2.2", "33", None), ("192.0.2.2", "24", "no-es-ip")],
)
def test_set_ip_rechaza_direcciones_invalidas(client, ip, mask, gateway):
    assert client.set_ip("em1", ip, mask, gateway)["ok"] is False


def test_set_ip_nombra_interfaz_logica_inexistente(monkeypatch, client):
    _captura_guardado(monkeypatch, client, _doc())
    result = client.set_ip("em9", "192.0.2.2", "24")
    assert result["ok"] is False
    assert "em9" in result["detail"]


@pytest.mark.parametrize(
    ("dns", "expected"),
    [(None, None), ("1.1.1.1", "1.1.1.1"), (["1.1.1.1", "8.8.8.8"], ["1.1.1.1", "8.8.8.8"])],
)
def test_dhcp_configura_rango_y_dns(monkeypatch, client, dns, expected):
    doc = _doc()
    _captura_guardado(monkeypatch, client, doc)

    result = client.dhcp("em1", "192.168.10.100", "192.168.10.200", dns=dns)

    assert result["ok"] is True
    values = doc["dhcpd"]["lan"]
    assert values["enable"] == ""
    assert values["range"] == {"from": "192.168.10.100", "to": "192.168.10.200"}
    assert values.get("dnsserver") == expected


@pytest.mark.parametrize(
    ("start", "end", "dns"),
    [("192.168.10.200", "192.168.10.100", None), ("no-es-ip", "192.168.10.200", None),
     ("192.168.10.100", "192.168.10.200", "no-es-ip")],
)
def test_dhcp_rechaza_rango_o_dns_invalidos(client, start, end, dns):
    assert client.dhcp("em1", start, end, dns=dns)["ok"] is False


def test_dhcp_nombra_interfaz_logica_inexistente(monkeypatch, client):
    _captura_guardado(monkeypatch, client, _doc())
    result = client.dhcp("em9", "192.168.10.100", "192.168.10.200")
    assert result["ok"] is False
    assert "em9" in result["detail"]


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("192.168.11.100", "192.168.11.200"),
        ("192.168.10.100", "192.168.11.200"),
    ],
)
def test_dhcp_rechaza_rango_fuera_de_la_red_sin_escribir(
    monkeypatch, client, start, end,
):
    doc = _doc()
    escrituras = []
    monkeypatch.setattr(client, "get_config", lambda: doc)
    monkeypatch.setattr(client, "put_config", lambda documento: (
        escrituras.append(documento) or {"ok": True}
    ))

    result = client.dhcp("em1", start, end)

    assert result["ok"] is False
    assert "192.168.10.0/24" in result["detail"]
    assert escrituras == []


@pytest.mark.parametrize(
    ("ifname", "interface"),
    [
        ("em1", {"if": "em1", "ipaddr": "dhcp", "subnet": ""}),
        ("lan", "valor-no-diccionario"),
    ],
)
def test_dhcp_rechaza_interfaz_sin_red_ipv4_estatica(
    monkeypatch, client, ifname, interface,
):
    doc = {"interfaces": {"lan": interface}}
    monkeypatch.setattr(client, "get_config", lambda: doc)
    monkeypatch.setattr(client, "put_config", lambda *args, **kwargs: pytest.fail("no debe escribir"))

    result = client.dhcp(ifname, "192.168.10.100", "192.168.10.200")

    assert result["ok"] is False
    assert "no se puede determinar la red IPv4" in result["detail"]


def test_rule_inserta_antes_del_reject_existente(monkeypatch, client):
    doc = _doc()
    _captura_guardado(monkeypatch, client, doc)

    result = client.rule(action="pass", ifname="lan", proto="tcp", src="any",
                         dst="203.0.113.0/24", port=80)

    assert result["ok"] is True
    rendered = pfsense.render_config(doc)
    rules = ET.fromstring(rendered).findall("filter/rule")
    acciones = [rule.findtext("type") for rule in rules]
    assert acciones == ["pass", "pass", "reject"]
    nueva = rules[1]
    assert nueva.findtext("interface") == "lan"
    assert nueva.findtext("protocol") == "tcp"
    assert nueva.findtext("destination/port") == "80"
    assert nueva.find("destination/network") is not None


def test_rule_crea_seccion_filter_sin_reglas(monkeypatch, client):
    doc = {"interfaces": {"lan": {"if": "em1"}}}
    _captura_guardado(monkeypatch, client, doc)

    assert client.rule()["ok"] is True
    assert doc["filter"]["rule"][0]["type"] == "pass"


def test_rule_acepta_filter_vacio_parseado(monkeypatch, client):
    doc = pfsense.parse_config(
        "<pfsense><interfaces><lan><if>em1</if></lan></interfaces><filter/></pfsense>"
    )
    _captura_guardado(monkeypatch, client, doc)

    result = client.rule()

    assert result["ok"] is True
    assert doc["filter"]["rule"][0]["type"] == "pass"
    assert ET.fromstring(pfsense.render_config(doc)).find("filter/rule") is not None


def test_rule_acepta_protocolo_sin_puerto_y_normaliza_minusculas(monkeypatch, client):
    doc = {"interfaces": {"lan": {"if": "em1"}}}
    _captura_guardado(monkeypatch, client, doc)

    assert client.rule(proto="ICMP")["ok"] is True
    assert doc["filter"]["rule"][0]["protocol"] == "icmp"


@pytest.mark.parametrize(
    ("kwargs", "mensaje"),
    [({"action": "drop"}, "acción"), ({"proto": "any", "port": 80}, "port"),
     ({"proto": "tcp", "port": 65536}, "port"), ({"proto": "nonsense"}, "protocolo")],
)
def test_rule_rechaza_accion_puerto_o_protocolo_invalidos(client, kwargs, mensaje):
    result = client.rule(**kwargs)
    assert result["ok"] is False
    assert mensaje in result["error"]


@pytest.mark.parametrize(
    ("src", "dst", "rechazado"),
    [
        ("no-es-ip", "any", "no-es-ip"),
        ("any", "999.999.999.999/99", "999.999.999.999/99"),
        ("any", "192.0.2.1/24", "192.0.2.1/24"),
        ("2001:db8::1", "any", "2001:db8::1"),
        ("", "any", "''"),
    ],
)
def test_rule_rechaza_extremos_ipv4_o_cidr_invalidos_sin_leer_config(
    monkeypatch, client, src, dst, rechazado,
):
    monkeypatch.setattr(client, "_run", lambda *args, **kwargs: pytest.fail("no debe leer config"))

    result = client.rule(src=src, dst=dst)

    assert result["ok"] is False
    assert rechazado in result["error"]


def test_rule_rechaza_interfaz_ausente_o_filter_no_diccionario(monkeypatch, client):
    doc = _doc()
    _captura_guardado(monkeypatch, client, doc)
    assert "em9" in client.rule(ifname="em9")["detail"]

    doc = _doc()
    doc["filter"] = "valor-no-diccionario"
    _captura_guardado(monkeypatch, client, doc)
    assert "filter" in client.rule()["detail"]


def test_nat_ida_y_vuelta_automatico_a_manual_no_deja_regla_sin_target(
    monkeypatch, client,
):
    doc = {"interfaces": {"wan": {"if": "em0"}}}
    _captura_guardado(monkeypatch, client, doc)

    assert client.nat("wan")["ok"] is True
    assert doc["nat"]["outbound"] == {"mode": "automatic"}

    assert client.nat("wan", target="203.0.113.1")["ok"] is True
    manual = doc["nat"]["outbound"]
    assert manual["mode"] == "manual"
    assert len(manual["rule"]) == 1
    assert manual["rule"][0]["target"] == "203.0.113.1"
    reparado = pfsense.parse_config(pfsense.render_config(doc))
    assert reparado["nat"]["outbound"]["rule"]["target"] == "203.0.113.1"


@pytest.mark.parametrize("target", [None, "203.0.113.1"])
def test_nat_fija_modo_y_solo_inserta_regla_manual(monkeypatch, client, target):
    doc = _doc()
    _captura_guardado(monkeypatch, client, doc)

    result = client.nat("wan", target=target)

    assert result["ok"] is True
    outbound = doc["nat"]["outbound"]
    assert outbound["mode"] == ("manual" if target is not None else "automatic")
    if target is None:
        assert outbound["rule"] == {"type": "reject", "interface": "wan"}
    else:
        assert outbound["rule"][0]["interface"] == "wan"
        assert outbound["rule"][0]["target"] == target
        assert outbound["rule"][1]["type"] == "reject"


def test_nat_rechaza_target_interfaz_u_outbound_invalidos(monkeypatch, client):
    assert client.nat(target="no-es-ip")["ok"] is False

    doc = _doc()
    _captura_guardado(monkeypatch, client, doc)
    assert "em9" in client.nat("em9")["detail"]

    doc = _doc()
    doc["nat"]["outbound"] = "valor-no-diccionario"
    _captura_guardado(monkeypatch, client, doc)
    assert client.nat()["ok"] is True
    assert doc["nat"]["outbound"]["mode"] == "automatic"


def test_enable_ssh_actualiza_system_y_valida_puerto(monkeypatch, client):
    doc = _doc()
    _captura_guardado(monkeypatch, client, doc)

    assert client.enable_ssh(2222)["ok"] is True
    assert doc["system"]["ssh"] == {"enable": "on", "port": "2222"}


@pytest.mark.parametrize("port", [0, 65536, "veintidos"])
def test_enable_ssh_rechaza_puerto_invalido(client, port):
    assert client.enable_ssh(port)["ok"] is False


def test_enable_ssh_reemplaza_seccion_ssh_no_diccionario(monkeypatch, client):
    doc = _doc()
    doc["system"]["ssh"] = "valor-no-diccionario"
    _captura_guardado(monkeypatch, client, doc)

    assert client.enable_ssh()["ok"] is True
    assert doc["system"]["ssh"]["port"] == "22022"
