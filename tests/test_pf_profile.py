"""Contrato del perfil pfSense declarativo: validación, plan, apply y status."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import textwrap
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import labspec  # noqa: E402
import pfsense  # noqa: E402

CLI_PATH = REPO / "cli" / "gns3lab"
LOADER = SourceFileLoader("gns3lab_pfprofiletests", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)

PERFIL = """\
version: 1
project: examen-kit
nodes:
  - name: PF1
    template: pfSense
    adapter_type: e1000
pfsense:
  project: examen-kit
  node: PF1
  lan_cidr: 192.168.56.0/24
  pfsense_ip: 192.168.56.1
  dhcp_from: 192.168.56.100
  dhcp_to: 192.168.56.199
  wan: CLOUD1
  disk: pfSense-examen.qcow2
  adapter_type: e1000
  console_type: telnet
  bridge: br-gns3-test
  host_ip: 192.168.56.254
  webui_name: pfsense-examen
"""


def _perfil(tmp_path, texto=PERFIL, nombre="examen.yaml") -> Path:
    ruta = tmp_path / nombre
    ruta.write_text(textwrap.dedent(texto), encoding="utf-8")
    return ruta


def _run_cli(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["gns3lab", *argv])
    try:
        return cli.main()
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1


# ───────────────────────────── validación ─────────────────────────────
def test_validar_y_normalizar_bloque_pfsense(tmp_path):
    ruta = _perfil(tmp_path)
    datos = labspec.leer(str(ruta))

    assert labspec.validar(datos) == []
    spec = labspec.normalizar(datos)
    assert spec["pfsense"]["project"] == "examen-kit"
    assert spec["pfsense"]["bridge"] == "br-gns3-test"
    assert spec["pfsense"]["adapter_type"] == "e1000"


def test_validar_rechaza_rango_fuera_de_subred_y_adaptador_no_e1000(tmp_path):
    texto = PERFIL.replace("192.168.56.199", "192.168.57.199").replace(
        "adapter_type: e1000\n  console_type", "adapter_type: virtio-net-pci\n  console_type")
    ruta = _perfil(tmp_path, texto)

    errores = labspec.validar(labspec.leer(str(ruta)))

    assert any("pfsense.dhcp_to" in error for error in errores), errores
    assert any("pfsense.adapter_type" in error for error in errores), errores


def test_validar_rechaza_secretos_en_el_perfil(tmp_path):
    texto = PERFIL + "  password: no-debe-ir-en-el-yaml\n"
    ruta = _perfil(tmp_path, texto)

    errores = labspec.validar(labspec.leer(str(ruta)))

    assert any("pfsense.password" in error and "desconocida" in error for error in errores)


def test_solape_de_subred_nombra_el_perfil_en_conflicto(tmp_path):
    _perfil(tmp_path)
    _perfil(tmp_path, PERFIL.replace("examen-kit", "otro-lab"), "otro.yaml")

    datos = labspec.leer(str(tmp_path / "examen.yaml"))
    vecinos = labspec.perfiles_vecinos(str(tmp_path / "examen.yaml"))
    errores = labspec.validar(datos, vecinos)

    assert any("se solapa" in error and "otro" in error for error in errores), errores
    assert any("192.168.56.0/24" in error for error in errores), errores


def test_dos_perfiles_con_subredes_distintas_no_se_solapan(tmp_path):
    _perfil(tmp_path)
    otro = PERFIL.replace("examen-kit", "otro-lab").replace(
        "192.168.56.", "192.168.57.").replace("br-gns3-test", "br-gns3-otro")
    _perfil(tmp_path, otro, "otro.yaml")

    datos = labspec.leer(str(tmp_path / "examen.yaml"))
    vecinos = labspec.perfiles_vecinos(str(tmp_path / "examen.yaml"))

    assert labspec.validar(datos, vecinos) == []


def test_plan_incluye_el_perfil_sin_ejecutar(tmp_path, capsys, monkeypatch):
    ruta = _perfil(tmp_path)
    monkeypatch.setattr(labspec, "ejecutar",
                        lambda *args, **kwargs: pytest.fail("plan no ejecuta"))

    assert labspec.main(["plan", str(ruta)]) == 0

    salida = capsys.readouterr().out
    assert "pf profile apply" in salida
    assert str(ruta) in salida


def test_verify_comprueba_el_perfil(tmp_path, capsys, monkeypatch):
    ruta = _perfil(tmp_path)
    spec = labspec.normalizar(labspec.leer(str(ruta)))

    def falso(argv, server=None):
        if argv[0] == "status":
            return 0, " * examen-kit abierto abcd1234\n      PF1 qemu started telnet:5000\n"
        if argv[:2] == ["pf", "detect"]:
            return 0, json.dumps({"ok": True, "data": {
                "project": "examen-kit", "node": "PF1",
                "wan": "em0", "lan": "em1", "adapter_type": "e1000"}})
        if argv[:2] == ["link", "list"]:
            return 0, ""
        if argv[:3] == ["pf", "profile", "status"]:
            return 0, "perfil pfSense: OK"
        raise AssertionError(f"orden inesperada: {argv}")

    monkeypatch.setattr(labspec, "capturar", falso)

    assert labspec.verificar(spec, None, spec_path=str(ruta)) == 0
    assert "perfil pfSense" in capsys.readouterr().out


# ───────────────────────────── CLI dry-run ─────────────────────────────
@pytest.fixture
def conf_local(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "CONF", tmp_path / "gns3lab.json")
    monkeypatch.setattr(cli, "load_conf", lambda: {"servers": {}, "default_server": "local"})


def test_profile_apply_dry_run_no_ejecuta_ip_ni_toca_gns3(
    monkeypatch, capsys, tmp_path, conf_local,
):
    ruta = _perfil(tmp_path)
    monkeypatch.setattr(cli, "_pf_ip_run", lambda argv: pytest.fail("dry-run ejecutó ip"))
    monkeypatch.setattr(cli, "_core_client", lambda server: pytest.fail("dry-run tocó GNS3"))

    rc = _run_cli(monkeypatch, ["pf", "profile", "apply", str(ruta), "--dry-run"])

    salida = capsys.readouterr().out
    assert rc == 0
    assert "ip link add name br-gns3-test type bridge" in salida
    assert "ip addr add 192.168.56.254/24 dev br-gns3-test" in salida
    assert "pf ip em1 192.168.56.1 24" in salida
    assert "pfsense-examen" in salida


def test_profile_apply_rechaza_solape_antes_de_tocar_nada(
    monkeypatch, capsys, tmp_path, conf_local,
):
    ruta = _perfil(tmp_path)
    _perfil(tmp_path, PERFIL.replace("examen-kit", "otro-lab"), "otro.yaml")
    monkeypatch.setattr(cli, "_pf_ip_run", lambda argv: pytest.fail("no debe tocar el host"))
    monkeypatch.setattr(cli, "_core_client", lambda server: pytest.fail("no debe tocar GNS3"))

    rc = _run_cli(monkeypatch, ["pf", "profile", "apply", str(ruta), "--yes"])

    texto = capsys.readouterr().err
    assert rc == 1
    assert "se solapa" in texto and "otro" in texto


def test_profile_apply_sin_yes_ni_dry_run_no_escribe(monkeypatch, capsys, tmp_path, conf_local):
    ruta = _perfil(tmp_path)
    monkeypatch.setattr(cli, "_pf_ip_run", lambda argv: pytest.fail("no debe escribir"))
    monkeypatch.setattr(cli, "_core_client", lambda server: pytest.fail("no debe tocar GNS3"))

    rc = _run_cli(monkeypatch, ["pf", "profile", "apply", str(ruta)])

    assert rc == 2
    assert "--yes" in capsys.readouterr().err


# ───────────────────────────── CLI apply/status ─────────────────────────────
class FakePf:
    """PfSense falso que mantiene el config.xml en memoria y registra llamadas."""

    def __init__(self, doc=None, error=None):
        self.doc = copy.deepcopy(doc or {})
        self.error = error
        self.calls = []
        self.host = None
        self.port = 22022

    def _role(self, ifname):
        for role, values in (self.doc.get("interfaces") or {}).items():
            if values.get("if") == ifname:
                return role
        return None

    def get_config(self):
        if self.error:
            raise RuntimeError(self.error)
        return copy.deepcopy(self.doc)

    def assign(self, mapping):
        self.calls.append(("assign", dict(mapping)))
        interfaces = self.doc.setdefault("interfaces", {})
        for role, ifname in mapping.items():
            interfaces[role] = {"if": ifname}
        return {"ok": True}

    def set_ip(self, ifname, ip, mask, gateway=None):
        self.calls.append(("ip", ifname, ip, mask))
        role = self._role(ifname) or "lan"
        self.doc["interfaces"][role].update(ipaddr=ip, subnet=str(mask))
        return {"ok": True}

    def dhcp(self, ifname, start, end, dns=None):
        self.calls.append(("dhcp", ifname, start, end))
        role = self._role(ifname) or "lan"
        self.doc.setdefault("dhcpd", {})[role] = {
            "enable": "", "range": {"from": start, "to": end}}
        return {"ok": True}

    def rule(self, action="pass", ifname="lan", proto="any", src="any",
             dst="any", port=None):
        self.calls.append(("rule", action, ifname, proto, src, dst))
        role = self._role(ifname) or "lan"
        filtro = self.doc.setdefault("filter", {})
        filtro.setdefault("rule", []).append({
            "type": action, "interface": role, "ipprotocol": "inet",
            "protocol": proto, "source": {"any": ""}, "destination": {"any": ""}})
        return {"ok": True}

    def nat(self, ifname="wan", target=None):
        self.calls.append(("nat", ifname, target))
        self.doc.setdefault("nat", {})["outbound"] = {"mode": "automatic"}
        return {"ok": True}

    def enable_ssh(self, port=22022):
        self.calls.append(("ssh", port))
        self.doc.setdefault("system", {})["ssh"] = {"enable": "on", "port": str(port)}
        return {"ok": True}


@pytest.fixture
def entorno_perfil(fake_api, monkeypatch, tmp_path):
    pid = "11111111-aaaa-bbbb-cccc-000000000033"
    proyecto = {"project_id": pid, "name": "examen-kit", "status": "opened"}
    nodo = {
        "node_id": "nodo-pf1", "name": "PF1", "node_type": "qemu",
        "console_type": "vnc",
        "properties": {"adapter_type": "virtio-net-pci",
                       "hda_disk_image": "otro.qcow2"},
        "status": "stopped",
    }
    cloud = {
        "node_id": "nodo-cloud1", "name": "CLOUD1", "node_type": "cloud",
        "console_type": "none",
        "properties": {"ports_mapping": [{
            "name": "eth0", "port_number": 0, "type": "ethernet",
            "interface": "virbr0"}]},
        "status": "started",
    }
    fake_api.set_projects([proyecto])
    fake_api.route("GET", f"/v2/projects/{pid}", 200, proyecto)
    fake_api.set_nodes(pid, [nodo, cloud])
    fake_api.route("PUT", f"/v2/projects/{pid}/nodes/nodo-pf1", 200, nodo)
    fake_api.route("PUT", f"/v2/projects/{pid}/nodes/nodo-cloud1", 200, cloud)

    conf = {"servers": {"prueba": {"url": fake_api.url, "auth": None}},
            "default_server": "prueba"}
    monkeypatch.setattr(cli, "CONF", tmp_path / "gns3lab.json")
    monkeypatch.setattr(cli, "load_conf", lambda: conf)
    monkeypatch.setenv("PFSENSE_PASSWORD", "secreto-de-prueba")
    monkeypatch.delenv("PFSENSE_HOST", raising=False)
    monkeypatch.delenv("PFSENSE_PORT", raising=False)

    estado_ip = {"link": False, "addr": False, "cmds": []}

    def ip_falso(argv):
        estado_ip["cmds"].append(list(argv))
        if argv[:3] == ["ip", "link", "show"]:
            return (0, "2: br-gns3-test: <BROADCAST> mtu 1500 state UP\n") if estado_ip["link"] else (1, "")
        if argv[:3] == ["ip", "link", "add"]:
            estado_ip["link"] = True
            return 0, ""
        if argv[:3] == ["ip", "link", "set"]:
            return 0, ""
        if argv[:4] == ["ip", "-4", "-o", "addr"]:
            texto = "2: br-gns3-test inet 192.168.56.254/24 scope global br-gns3-test\n" \
                if estado_ip["addr"] else ""
            return (0, texto) if estado_ip["link"] else (1, "")
        if argv[:3] == ["ip", "addr", "add"]:
            estado_ip["addr"] = True
            return 0, ""
        raise AssertionError(f"ip inesperado: {argv}")

    monkeypatch.setattr(cli, "_pf_ip_run", ip_falso)
    falso = FakePf()
    monkeypatch.setattr(pfsense.PfSense, "from_env", classmethod(lambda cls: falso))
    return {"api": fake_api, "pid": pid, "nodo": nodo, "cloud": cloud,
            "ip": estado_ip, "pf": falso, "ruta": _perfil(tmp_path)}


def test_profile_apply_asegura_bridge_nodo_cloud_y_config(entorno_perfil, monkeypatch, capsys):
    entorno = entorno_perfil

    rc = _run_cli(monkeypatch, [
        "pf", "profile", "apply", str(entorno["ruta"]), "--yes"])

    salida = capsys.readouterr().out
    assert rc == 0, salida
    assert entorno["ip"]["link"] is True and entorno["ip"]["addr"] is True
    puts = [r for r in entorno["api"].requests if r["method"] == "PUT"]
    cuerpos = [json.loads(r["body"]) for r in puts]
    assert any(c.get("console_type") == "telnet" for c in cuerpos), cuerpos
    assert any((c.get("properties") or {}).get("adapter_type") == "e1000" for c in cuerpos), cuerpos
    mapeo = [c for c in cuerpos if "ports_mapping" in (c.get("properties") or {})]
    assert mapeo and mapeo[0]["properties"]["ports_mapping"][0]["interface"] == "br-gns3-test"
    assert [c[0] for c in entorno["pf"].calls] == [
        "assign", "ip", "dhcp", "rule", "nat", "ssh"]
    assert "https://pfsense-examen" in salida


def test_profile_apply_es_idempotente(entorno_perfil, monkeypatch, capsys):
    entorno = entorno_perfil
    assert _run_cli(monkeypatch, [
        "pf", "profile", "apply", str(entorno["ruta"]), "--yes"]) == 0

    # El servidor ya refleja los cambios del primer apply.
    nodo = copy.deepcopy(entorno["nodo"])
    nodo["console_type"] = "telnet"
    nodo["properties"] = {"adapter_type": "e1000",
                          "hda_disk_image": "pfSense-examen.qcow2"}
    cloud = copy.deepcopy(entorno["cloud"])
    cloud["properties"]["ports_mapping"][0]["interface"] = "br-gns3-test"
    entorno["api"].set_nodes(entorno["pid"], [nodo, cloud])
    entorno["ip"]["cmds"].clear()
    llamadas_pf = len(entorno["pf"].calls)
    puts_antes = len([r for r in entorno["api"].requests if r["method"] == "PUT"])
    capsys.readouterr()

    rc = _run_cli(monkeypatch, [
        "pf", "profile", "apply", str(entorno["ruta"]), "--yes"])

    assert rc == 0
    assert len(entorno["pf"].calls) == llamadas_pf
    assert len([r for r in entorno["api"].requests if r["method"] == "PUT"]) == puts_antes
    assert not any(argv[:3] in (["ip", "link", "add"], ["ip", "addr", "add"])
                   for argv in entorno["ip"]["cmds"])
    assert "sin cambios" in capsys.readouterr().out


def test_profile_status_detecta_deriva_sin_escribir(entorno_perfil, monkeypatch, capsys):
    entorno = entorno_perfil
    assert _run_cli(monkeypatch, [
        "pf", "profile", "apply", str(entorno["ruta"]), "--yes"]) == 0
    nodo = copy.deepcopy(entorno["nodo"])
    nodo["console_type"] = "telnet"
    nodo["properties"] = {"adapter_type": "e1000",
                          "hda_disk_image": "pfSense-examen.qcow2"}
    cloud = copy.deepcopy(entorno["cloud"])
    cloud["properties"]["ports_mapping"][0]["interface"] = "br-gns3-test"
    entorno["api"].set_nodes(entorno["pid"], [nodo, cloud])
    puts_antes = len([r for r in entorno["api"].requests if r["method"] == "PUT"])
    capsys.readouterr()

    rc = _run_cli(monkeypatch, ["pf", "profile", "status", str(entorno["ruta"])])

    salida = capsys.readouterr().out
    assert rc == 0, salida
    assert "sin deriva" in salida
    assert len([r for r in entorno["api"].requests if r["method"] == "PUT"]) == puts_antes

    nodo["console_type"] = "vnc"
    entorno["api"].set_nodes(entorno["pid"], [nodo, cloud])

    rc = _run_cli(monkeypatch, ["pf", "profile", "status", str(entorno["ruta"])])

    salida = capsys.readouterr().out
    assert rc == 1
    assert "console_type" in salida
    assert len([r for r in entorno["api"].requests if r["method"] == "PUT"]) == puts_antes


def test_profile_status_detecta_deriva_de_config_sin_escribir(
    entorno_perfil, monkeypatch, capsys,
):
    entorno = entorno_perfil
    assert _run_cli(monkeypatch, [
        "pf", "profile", "apply", str(entorno["ruta"]), "--yes"]) == 0
    nodo = copy.deepcopy(entorno["nodo"])
    nodo["console_type"] = "telnet"
    nodo["properties"] = {"adapter_type": "e1000",
                          "hda_disk_image": "pfSense-examen.qcow2"}
    cloud = copy.deepcopy(entorno["cloud"])
    cloud["properties"]["ports_mapping"][0]["interface"] = "br-gns3-test"
    entorno["api"].set_nodes(entorno["pid"], [nodo, cloud])
    entorno["pf"].doc["interfaces"]["lan"]["ipaddr"] = "10.0.0.1"
    capsys.readouterr()

    rc = _run_cli(monkeypatch, ["pf", "profile", "status", str(entorno["ruta"])])

    salida = capsys.readouterr().out
    assert rc == 1
    assert "pf: deriva en ip" in salida


def test_profile_apply_no_filtra_la_contrasena(entorno_perfil, monkeypatch, capsys):
    entorno = entorno_perfil
    entorno["pf"].error = "fallo con secreto-de-prueba"

    rc = _run_cli(monkeypatch, [
        "pf", "profile", "apply", str(entorno["ruta"]), "--yes"])

    capturado = capsys.readouterr()
    texto = capturado.out + capturado.err
    assert rc == 1
    assert "secreto-de-prueba" not in texto
    assert "PFSENSE_PASSWORD" in texto or "***" in texto
