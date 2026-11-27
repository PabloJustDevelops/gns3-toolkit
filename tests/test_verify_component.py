"""Contrato de `gns3lab verify` / `gns3_verify`: solo lectura y verde/rojo por check.

Usa los dobles de `conftest.py` (API REST, consola telnet y monitor HMP). No abre
proyectos ni arranca nodos: un proyecto cerrado se reporta como problema.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

import pytest

import gns3core as core

try:
    import pfsense
except ModuleNotFoundError as exc:  # pragma: no cover - pfsense vive en la raíz
    if exc.name != "pfsense":
        raise
    pfsense = None

import gns3_mcp_server as server

CLI_PATH = Path(__file__).resolve().parents[1] / "cli" / "gns3lab"
LOADER = SourceFileLoader("gns3lab_verifytests", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)

PID = "11111111-aaaa-bbbb-cccc-000000000001"


@pytest.fixture(autouse=True)
def limpia_entorno_pfsense(monkeypatch):
    for name in ("PFSENSE_HOST", "PFSENSE_USER", "PFSENSE_PASSWORD", "PFSENSE_PORT"):
        monkeypatch.delenv(name, raising=False)


def _proyecto(status="opened"):
    return {"project_id": PID, "name": "lab-prueba", "status": status}


def _qemu(**props):
    base = {"node_id": "nodo-qemu-1", "name": "PC-QEMU", "node_type": "qemu",
            "status": "started", "properties": {"adapter_type": "e1000"}}
    base["properties"].update(props)
    return base


def _pf_node(**props):
    base = {"node_id": "nodo-pfsense", "name": "pfSense", "node_type": "qemu",
            "status": "started",
            "properties": {"adapter_type": "e1000", "hda_disk_image": "pfSense.qcow2"}}
    base["properties"].update(props)
    return base


def _vpcs(port, status="started"):
    return {"node_id": "nodo-vpcs-1", "name": "PC1", "node_type": "vpcs",
            "status": status, "console": port, "console_type": "telnet"}


def _setup(fake_api, nodes, status="opened"):
    fake_api.set_projects([_proyecto(status)])
    fake_api.set_nodes(PID, nodes)


def _cli_conf(monkeypatch, tmp_path, fake_api):
    conf = {
        "servers": {"prueba": {"url": fake_api.url, "auth": None}},
        "default_server": "prueba",
    }
    conf_path = tmp_path / "gns3lab.json"
    conf_path.write_text("{}")
    monkeypatch.setattr(cli, "CONF", conf_path)
    monkeypatch.setattr(cli, "load_conf", lambda: conf)
    return conf


def _run_cli(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["gns3lab", *argv])
    try:
        return cli.main()
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1


def _checks(result):
    return {c["name"]: c for c in result["checks"]}


def _config_valida():
    return {
        "system": {"hostname": "fw"},
        "interfaces": {
            "wan": {"if": "em0"},
            "lan": {"if": "em1", "ipaddr": "192.168.10.1", "subnet": "255.255.255.0"},
        },
        "filter": {"rule": [{"type": "pass", "interface": "lan",
                             "source": {"any": ""}, "destination": {"any": ""}}]},
        "nat": {"outbound": {"mode": "automatic"}},
        "dhcpd": {"lan": {"enable": "", "range": {"from": "192.168.10.100",
                                                  "to": "192.168.10.200"}}},
    }


def _pf_falso(monkeypatch, doc):
    llamadas = {"get": 0}

    class Falso:
        def get_config(self):
            llamadas["get"] += 1
            return doc

        def put_config(self, *args, **kwargs):
            raise AssertionError("verify no puede escribir en el firewall")

        def __getattr__(self, name):
            raise AssertionError(f"verify no debe llamar a PfSense.{name}")

    monkeypatch.setenv("PFSENSE_PASSWORD", "clave-de-prueba")
    monkeypatch.setattr(pfsense.PfSense, "from_env", classmethod(lambda cls: Falso()))
    return llamadas


# ───────────────────────────── qemu ─────────────────────────────
def test_qemu_verde_por_api_y_hmp(fake_api, hmp_factory, monkeypatch):
    _setup(fake_api, [_qemu()])
    hmp = hmp_factory()
    monkeypatch.setattr(core, "find_monitor_port", lambda *a, **kw: hmp.port)

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "qemu")

    assert resultado["component"] == "qemu"
    assert resultado["project"] == "lab-prueba"
    assert resultado["ok"] is True, resultado
    assert resultado["problems"] == []
    checks = _checks(resultado)
    assert checks["nodo"]["ok"] is True
    assert checks["estado"]["ok"] is True
    assert checks["adapter_type"]["ok"] is True
    assert checks["puerto HMP"]["ok"] is True
    assert checks["info status"]["ok"] is True
    assert "info status" in hmp.commands


def test_qemu_rojo_si_el_nodo_esta_parado(fake_api, monkeypatch):
    _setup(fake_api, [_qemu() | {"status": "stopped"}])
    monkeypatch.setattr(core, "find_monitor_port", lambda *a, **kw: None)

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "qemu")

    assert resultado["ok"] is False
    checks = _checks(resultado)
    assert checks["estado"]["ok"] is False
    assert checks["puerto HMP"]["ok"] is False
    assert any("estado" in p for p in resultado["problems"])


def test_qemu_rojo_si_falta_adapter_type(fake_api, hmp_factory, monkeypatch):
    node = _qemu()
    node["properties"] = {}
    _setup(fake_api, [node])
    hmp = hmp_factory()
    monkeypatch.setattr(core, "find_monitor_port", lambda *a, **kw: hmp.port)

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "qemu")

    assert resultado["ok"] is False
    assert _checks(resultado)["adapter_type"]["ok"] is False


def test_qemu_rojo_si_el_monitor_no_responde(fake_api, monkeypatch):
    _setup(fake_api, [_qemu()])
    monkeypatch.setattr(core, "find_monitor_port", lambda *a, **kw: 1)

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "qemu")

    assert resultado["ok"] is False
    assert _checks(resultado)["info status"]["ok"] is False


def test_qemu_sin_nodo_qemu_es_accionable(fake_api):
    _setup(fake_api, [_vpcs(5001)])

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "qemu")

    assert resultado["ok"] is False
    assert _checks(resultado)["nodo"]["ok"] is False
    assert "qemu" in _checks(resultado)["nodo"]["detail"].lower()


# ───────────────────────────── pfSense ─────────────────────────────
def test_pf_verde_con_detect_y_config_sin_escribir(fake_api, monkeypatch):
    _setup(fake_api, [_pf_node()])
    llamadas = _pf_falso(monkeypatch, _config_valida())

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "pf")

    assert resultado["ok"] is True, resultado
    checks = _checks(resultado)
    assert checks["interfaces"]["ok"] is True
    assert checks["PFSENSE_PASSWORD"]["ok"] is True
    assert checks["secciones"]["ok"] is True
    assert checks["interfaces configuradas"]["ok"] is True
    assert checks["reglas"]["ok"] is True
    assert checks["NAT"]["ok"] is True
    assert checks["DHCP"]["ok"] is True
    assert llamadas["get"] == 1
    assert all(req["method"] == "GET" for req in fake_api.requests)


def test_pf_sin_password_nombra_la_variable_y_no_lee_config(fake_api, monkeypatch):
    _setup(fake_api, [_pf_node()])
    _pf_falso(monkeypatch, _config_valida())
    monkeypatch.delenv("PFSENSE_PASSWORD", raising=False)

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "pf")

    texto = json.dumps(resultado, ensure_ascii=False)
    assert resultado["ok"] is False
    checks = _checks(resultado)
    assert checks["PFSENSE_PASSWORD"]["ok"] is False
    assert checks["config.xml"]["ok"] is False
    assert "PFSENSE_PASSWORD" in texto
    assert "PFSENSE_PASSWORD=" not in texto


def test_pf_interfaces_incoherentes(fake_api, monkeypatch):
    _setup(fake_api, [_pf_node()])
    doc = _config_valida()
    doc["interfaces"]["lan"]["if"] = "vtnet1"
    _pf_falso(monkeypatch, doc)

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "pf")

    assert resultado["ok"] is False
    check = _checks(resultado)["interfaces configuradas"]
    assert check["ok"] is False
    assert "em1" in check["detail"]


def test_pf_secciones_ausentes(fake_api, monkeypatch):
    _setup(fake_api, [_pf_node()])
    doc = _config_valida()
    del doc["filter"], doc["nat"], doc["dhcpd"]
    _pf_falso(monkeypatch, doc)

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "pf")

    assert resultado["ok"] is False
    checks = _checks(resultado)
    assert checks["secciones"]["ok"] is False
    assert checks["reglas"]["ok"] is False
    assert checks["NAT"]["ok"] is False
    assert checks["DHCP"]["ok"] is False


def test_pf_dhcp_fuera_de_la_red_lan(fake_api, monkeypatch):
    _setup(fake_api, [_pf_node()])
    doc = _config_valida()
    doc["dhcpd"]["lan"]["range"] = {"from": "10.0.0.10", "to": "10.0.0.20"}
    _pf_falso(monkeypatch, doc)

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "pf")

    assert resultado["ok"] is False
    assert _checks(resultado)["DHCP"]["ok"] is False


def test_pf_ssh_caido_reporta_error_literal(fake_api, monkeypatch):
    _setup(fake_api, [_pf_node()])
    _pf_falso(monkeypatch, {"ok": False, "error": "ssh: connection refused"})

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "pf")

    assert resultado["ok"] is False
    assert "ssh: connection refused" in _checks(resultado)["config.xml"]["detail"]


# ───────────────────────────── vpcs ─────────────────────────────
def test_vpcs_verde_por_consola_telnet(fake_api, telnet_factory):
    salida = (
        "PC1> show ip\r\n\r\n"
        "NAME        : PC1[1]\r\n"
        "IP/MASK     : 192.168.10.10/24\r\n"
        "GATEWAY     : 192.168.10.1\r\n"
        "DHCP SERVER : 192.168.10.1\r\n"
        "\r\nPC1> "
    )
    fake = telnet_factory(on_line=lambda linea: salida.encode() if linea.strip() == "show ip" else b"")
    _setup(fake_api, [_vpcs(fake.port)])

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "vpcs")

    assert resultado["ok"] is True, resultado
    checks = _checks(resultado)
    assert checks["consola"]["ok"] is True
    assert checks["show ip"]["ok"] is True
    assert checks["gateway"]["ok"] is True
    assert "192.168.10.1" in checks["gateway"]["detail"]
    assert "show ip" in fake.lines


@pytest.mark.parametrize("gateway", ["192.168.10.255", "192.168.11.0"])
def test_vpcs_acepta_gateway_de_host_en_red_23(fake_api, telnet_factory, gateway):
    salida = (
        "PC1> show ip\r\nIP/MASK     : 192.168.10.10/23\r\n"
        f"GATEWAY     : {gateway}\r\nPC1> "
    )
    fake = telnet_factory(on_line=lambda linea: salida.encode() if linea.strip() == "show ip" else b"")
    _setup(fake_api, [_vpcs(fake.port)])

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "vpcs")

    assert resultado["ok"] is True, resultado
    check = _checks(resultado)["gateway"]
    assert check["ok"] is True
    assert gateway in check["detail"]
    assert "máscara" not in check["detail"]


@pytest.mark.parametrize("gateway", ["192.168.10.0", "192.168.10.255"])
def test_vpcs_rechaza_direccion_de_red_y_difusion_en_red_24(fake_api, telnet_factory, gateway):
    salida = (
        "PC1> show ip\r\nIP/MASK     : 192.168.10.10/24\r\n"
        f"GATEWAY     : {gateway}\r\nPC1> "
    )
    fake = telnet_factory(on_line=lambda linea: salida.encode() if linea.strip() == "show ip" else b"")
    _setup(fake_api, [_vpcs(fake.port)])

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "vpcs")

    assert resultado["ok"] is False
    assert _checks(resultado)["gateway"]["ok"] is False


def test_vpcs_sin_ip_no_se_da_por_listo(fake_api, telnet_factory):
    fake = telnet_factory(on_line=lambda linea: (
        "PC1> show ip\r\nIP/MASK     : 0.0.0.0/0\r\nGATEWAY     : 0.0.0.0\r\nPC1> "
    ).encode() if linea.strip() == "show ip" else b"")
    _setup(fake_api, [_vpcs(fake.port)])

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "vpcs")

    assert resultado["ok"] is False
    assert _checks(resultado)["show ip"]["ok"] is False


def test_vpcs_gateway_sospechosa_es_la_mascara(fake_api, telnet_factory):
    fake = telnet_factory(on_line=lambda linea: (
        "PC1> show ip\r\nIP/MASK     : 192.168.10.10/24\r\nGATEWAY     : 255.255.255.0\r\nPC1> "
    ).encode() if linea.strip() == "show ip" else b"")
    _setup(fake_api, [_vpcs(fake.port)])

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "vpcs")

    assert resultado["ok"] is False
    check = _checks(resultado)["gateway"]
    assert check["ok"] is False
    assert "máscara" in check["detail"]


def test_vpcs_consola_inalcanzable(fake_api, telnet_factory):
    fake = telnet_factory()
    fake.close()
    _setup(fake_api, [_vpcs(fake.port)])

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "vpcs")

    assert resultado["ok"] is False
    assert _checks(resultado)["consola"]["ok"] is False


# ───────────────────── proyecto, componente y contrato ─────────────────────
def test_proyecto_cerrado_no_se_abre(fake_api):
    _setup(fake_api, [_qemu()], status="closed")

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "qemu")

    assert resultado["ok"] is False
    assert _checks(resultado)["proyecto abierto"]["ok"] is False
    assert "abre" in resultado["problems"][0].lower() or "open" in resultado["problems"][0].lower()
    assert all(req["method"] == "GET" for req in fake_api.requests), \
        "verify no puede abrir el proyecto"


def test_componente_desconocido(fake_api):
    _setup(fake_api, [_qemu()])

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "docker")

    assert resultado["ok"] is False
    assert "docker" in resultado["problems"][0]


def test_cli_verify_json_y_exit_code(fake_api, hmp_factory, monkeypatch, capsys, tmp_path):
    _setup(fake_api, [_qemu()])
    hmp = hmp_factory()
    monkeypatch.setattr(core, "find_monitor_port", lambda *a, **kw: hmp.port)
    _cli_conf(monkeypatch, tmp_path, fake_api)

    rc = _run_cli(monkeypatch, ["verify", "qemu", "lab-prueba", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["component"] == "qemu"
    assert payload["project"] == "lab-prueba"
    assert payload["ok"] is True
    assert {"component", "project", "ok", "checks", "problems"} <= set(payload)


def test_cli_verify_devuelve_1_cuando_un_check_falla(fake_api, monkeypatch, capsys, tmp_path):
    _setup(fake_api, [_qemu() | {"status": "stopped"}])
    monkeypatch.setattr(core, "find_monitor_port", lambda *a, **kw: None)
    _cli_conf(monkeypatch, tmp_path, fake_api)

    rc = _run_cli(monkeypatch, ["verify", "qemu", "lab-prueba", "--json"])

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["problems"]


def test_cli_verify_no_imprime_secretos(fake_api, monkeypatch, capsys, tmp_path):
    secreto = "clave-que-no-sale-012345"
    monkeypatch.setenv("PFSENSE_PASSWORD", secreto)
    _setup(fake_api, [_pf_node()])

    class Falso:
        def get_config(self):
            return _config_valida()

    monkeypatch.setattr(pfsense.PfSense, "from_env", classmethod(lambda cls: Falso()))
    _cli_conf(monkeypatch, tmp_path, fake_api)

    rc = _run_cli(monkeypatch, ["verify", "pf", "lab-prueba", "--json"])

    salida = capsys.readouterr().out
    assert rc == 0
    assert secreto not in salida
    assert "PFSENSE_PASSWORD" not in salida or "PFSENSE_PASSWORD=" not in salida


def test_mcp_verify_comparte_contrato(fake_api, hmp_factory, monkeypatch):
    _setup(fake_api, [_qemu()])
    hmp = hmp_factory()
    monkeypatch.setattr(core, "find_monitor_port", lambda *a, **kw: hmp.port)
    monkeypatch.setattr(server, "_conf", lambda: {
        "url": fake_api.url, "user": "u", "password": "p"})

    resultado = server.gns3_verify(component="qemu", project="lab-prueba")

    assert resultado["component"] == "qemu"
    assert resultado["project"] == "lab-prueba"
    assert resultado["ok"] is True
    assert resultado["problems"] == []


def test_mcp_verify_componente_invalido():
    resultado = server.gns3_verify(component="docker")

    assert resultado["ok"] is False
    assert "docker" in resultado["problems"][0]


# ───────────────── ramas de selección, errores y formatos raros ─────────────────
def test_vlist_normaliza_escalar():
    assert core._vlist("uno") == ["uno"]
    assert core._vlist(None) == []
    assert core._vlist(["uno"]) == ["uno"]


@pytest.mark.parametrize("pedido", ["PC1", "PC"])
def test_verify_selecciona_el_nodo_pedido(fake_api, hmp_factory, monkeypatch, pedido):
    _setup(fake_api, [_qemu() | {"name": "OTRO"}, _qemu() | {"name": "PC1"}])
    hmp = hmp_factory()
    monkeypatch.setattr(core, "find_monitor_port", lambda *a, **kw: hmp.port)

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba",
                                      "qemu", node=pedido)

    assert resultado["ok"] is True, resultado
    assert "PC1" in _checks(resultado)["nodo"]["detail"]


def test_verify_node_inexistente(fake_api):
    _setup(fake_api, [_qemu()])

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba",
                                      "qemu", node="NO-EXISTE")

    assert resultado["ok"] is False
    assert "NO-EXISTE" in _checks(resultado)["nodo"]["detail"]


def test_verify_varios_nodos_pide_node(fake_api):
    _setup(fake_api, [_vpcs(5001), _vpcs(5002) | {"name": "PC2", "node_id": "nodo-vpcs-2"}])

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "vpcs")

    assert resultado["ok"] is False
    check = _checks(resultado)["nodo"]
    assert check["ok"] is False
    assert "--node" in check["detail"]


def test_pf_regla_y_nat_escalares_se_normalizan(fake_api, monkeypatch):
    _setup(fake_api, [_pf_node()])
    doc = _config_valida()
    doc["filter"]["rule"] = {"type": "pass", "interface": "lan"}
    doc["nat"]["outbound"] = {"mode": "manual",
                              "rule": {"interface": "wan", "source": {"any": ""},
                                       "destination": {"any": ""}}}
    _pf_falso(monkeypatch, doc)

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "pf")

    assert resultado["ok"] is True, resultado


def test_pf_sin_subnet_lan_no_revienta(fake_api, monkeypatch):
    _setup(fake_api, [_pf_node()])
    doc = _config_valida()
    doc["interfaces"]["lan"].pop("ipaddr")
    doc["interfaces"]["lan"].pop("subnet")
    _pf_falso(monkeypatch, doc)

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "pf")

    assert _checks(resultado)["DHCP"]["ok"] is True
    assert "no calculable" in _checks(resultado)["DHCP"]["detail"]


def test_pf_sin_modulo_pfsense(monkeypatch):
    monkeypatch.setitem(sys.modules, "pfsense", None)

    checks = core._verify_pf_checks(_pf_node())

    assert checks[0]["ok"] is False
    assert "pfsense.py" in checks[0]["detail"]


def test_pf_adapter_desconocido_y_sin_password(fake_api, monkeypatch):
    _setup(fake_api, [_pf_node(adapter_type="ne2k_pci")])

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "pf")

    assert resultado["ok"] is False
    assert _checks(resultado)["interfaces"]["ok"] is False
    assert _checks(resultado)["PFSENSE_PASSWORD"]["ok"] is False


def test_pf_from_env_falla(monkeypatch):
    monkeypatch.setenv("PFSENSE_PASSWORD", "clave-de-prueba")

    def rompe():
        raise pfsense.PfSenseError("entorno incompleto")

    monkeypatch.setattr(pfsense.PfSense, "from_env", classmethod(lambda cls: rompe()))

    checks = core._verify_pf_checks(_pf_node())

    assert _checks({"checks": checks})["config.xml"]["ok"] is False
    assert "entorno incompleto" in _checks({"checks": checks})["config.xml"]["detail"]


def test_vpcs_sin_consola_telnet(fake_api):
    _setup(fake_api, [_vpcs(0) | {"console_type": "none"}])

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "vpcs")

    assert resultado["ok"] is False
    assert _checks(resultado)["consola"]["ok"] is False


def test_vpcs_sin_gateway(fake_api, telnet_factory):
    fake = telnet_factory(on_line=lambda linea: (
        "PC1> show ip\r\nIP/MASK     : 192.168.10.10/24\r\nPC1> "
    ).encode() if linea.strip() == "show ip" else b"")
    _setup(fake_api, [_vpcs(fake.port)])

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "vpcs")

    assert resultado["ok"] is False
    assert "GATEWAY" in _checks(resultado)["gateway"]["detail"]


def test_vpcs_ip_invalida_no_revienta(fake_api, telnet_factory):
    fake = telnet_factory(on_line=lambda linea: (
        "PC1> show ip\r\nIP/MASK     : 999.999.999.999/24\r\n"
        "GATEWAY     : 192.168.10.1\r\nPC1> "
    ).encode() if linea.strip() == "show ip" else b"")
    _setup(fake_api, [_vpcs(fake.port)])

    resultado = core.verify_component(core.Client(fake_api.url), "lab-prueba", "vpcs")

    assert resultado["ok"] is False
    assert _checks(resultado)["gateway"]["ok"] is False


def test_proyecto_inexistente(fake_api):
    _setup(fake_api, [_qemu()])

    resultado = core.verify_component(core.Client(fake_api.url), "no-existe", "qemu")

    assert resultado["ok"] is False
    assert _checks(resultado)["proyecto"]["ok"] is False


def test_error_al_listar_nodos():
    class ClienteRoto:
        def resolve_project(self, _project):
            return _proyecto()

        def nodes(self, _pid):
            raise RuntimeError("la API devolvió 500")

    resultado = core.verify_component(ClienteRoto(), "lab-prueba", "qemu")

    assert resultado["ok"] is False
    assert "500" in _checks(resultado)["nodos"]["detail"]
