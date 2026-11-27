"""Spec declarativo: validación, plan y guardas de escritura de scripts/labspec.py."""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import labspec  # noqa: E402  (módulo sin dependencias del servidor)
import pfsense  # noqa: E402

EJEMPLO = REPO / "examples" / "lab-ejemplo.yaml"


def escribir(tmp_path, texto):
    ruta = tmp_path / "lab.yaml"
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def test_ejemplo_valida(tmp_path, capsys):
    assert EJEMPLO.is_file(), f"falta {EJEMPLO}"
    assert labspec.main(["validate", str(EJEMPLO)]) == 0
    salida = capsys.readouterr().out
    assert "OK" in salida


def test_validate_acumula_errores_con_ruta(tmp_path, capsys):
    ruta = escribir(tmp_path, """\
version: 2
project: ""
nodes:
  - name: pc1
    template: VPCS
    ip: 999.1.1.1/24
  - name: pc1
    template: ""
links:
  - a: pc1
    b: noexiste
    pa: -1
expect:
  noexiste:
    - show ip
""")
    assert labspec.main(["validate", str(ruta)]) == 1
    salida = capsys.readouterr().out
    for ruta_campo in ("version", "project", "nodes[0].ip", "nodes[1].name",
                       "nodes[1].template", "links[0].b", "links[0].pa",
                       "expect.noexiste"):
        assert ruta_campo in salida, (ruta_campo, salida)


def test_yaml_invalido_devuelve_1(tmp_path, capsys):
    ruta = escribir(tmp_path, "version: [1\n")
    assert labspec.main(["validate", str(ruta)]) == 1
    assert "YAML" in capsys.readouterr().out


def test_plan_imprime_ordenes_sin_ejecutar(monkeypatch, capsys):
    llamadas = []
    monkeypatch.setattr(labspec, "ejecutar", lambda argv, server=None: llamadas.append(argv) or 0)
    assert labspec.main(["plan", str(EJEMPLO)]) == 0
    assert llamadas == []
    lineas = [l for l in capsys.readouterr().out.splitlines() if l.startswith("gns3lab ")]
    assert lineas[0] == "gns3lab new lab-ejemplo"
    assert any("node add --template VPCS --name pc1" in l for l in lineas)
    assert any("link add pc1 sw1 --pa 0 --pb 0" in l for l in lineas)
    assert lineas[-1] == "gns3lab up lab-ejemplo"


def test_apply_sin_yes_no_escribe(monkeypatch, capsys):
    llamadas = []
    monkeypatch.setattr(labspec, "ejecutar", lambda argv, server=None: llamadas.append(argv) or 0)
    assert labspec.main(["apply", str(EJEMPLO)]) == 2
    assert llamadas == []
    assert "--yes" in capsys.readouterr().err


def test_apply_con_yes_ejecuta_en_orden(monkeypatch, capsys):
    llamadas = []
    monkeypatch.setattr(labspec, "ejecutar", lambda argv, server=None: llamadas.append(list(argv)) or 0)
    assert labspec.main(["apply", "--yes", str(EJEMPLO)]) == 0
    assert llamadas[0] == ["new", "lab-ejemplo"]
    assert llamadas[-1] == ["up", "lab-ejemplo"]
    assert any(argv[:2] == ["link", "add"] for argv in llamadas)
    assert capsys.readouterr().out.count("gns3lab ") >= len(llamadas)


def test_apply_se_para_en_el_primer_fallo(monkeypatch, capsys):
    llamadas = []

    def falla(argv, server=None):
        llamadas.append(list(argv))
        return 1

    monkeypatch.setattr(labspec, "ejecutar", falla)
    assert labspec.main(["apply", "--yes", str(EJEMPLO)]) == 1
    assert len(llamadas) == 1


def test_verify_ok_parsea_status_enlaces_y_expect(monkeypatch, capsys):
    salidas = {
        ("status", "lab-ejemplo"): (
            0,
            " * lab-ejemplo                      abierto  abcd1234\n"
            "      pc1              vpcs             started   telnet:5000\n"
            "      pc2              vpcs             started   telnet:5001\n"
            "      sw1              ethernet_switch  started   telnet:5002\n"),
        ("link", "list", "-p", "lab-ejemplo"): (
            0,
            "  aaaaaaaa  pc1:0/0 <-> sw1:0/0\n"
            "  bbbbbbbb  pc2:0/0 <-> sw1:1/0\n"),
    }

    def falso(argv, server=None):
        clave = tuple(argv)
        if clave in salidas:
            return salidas[clave]
        if argv[0] == "exec":
            return 0, f"$ {argv[2]}\nIP/Mask : 0.0.0.0/0\n"
        raise AssertionError(f"orden inesperada: {argv}")

    monkeypatch.setattr(labspec, "capturar", falso)
    assert labspec.main(["verify", str(EJEMPLO)]) == 0
    salida = capsys.readouterr().out
    assert "pc1" in salida and "sw1" in salida
    assert "RESULTADO: OK" in salida


def test_verify_usa_adapter_type_devuelto_por_pf_detect(monkeypatch, capsys):
    nodo = {"name": "fw", "properties": {"adapter_type": "e1000"}}
    spec = {
        "version": 1, "project": "p", "links": [], "expect": {},
        "nodes": [{"name": "fw", "template": "pfSense", "adapter_type": "e1000"}],
    }

    def falso(argv, server=None):
        if argv[0] == "status":
            return 0, " * p abierto abcd1234\n      fw qemu started telnet:5000\n"
        if argv[:2] == ["pf", "detect"]:
            data = {"project": "p", "node": "fw", **pfsense.detect_ifnames(nodo)}
            return 0, json.dumps({"ok": True, "data": data})
        if argv[:2] == ["link", "list"]:
            return 0, ""
        raise AssertionError(f"orden inesperada: {argv}")

    monkeypatch.setattr(labspec, "capturar", falso)

    assert labspec.verificar(spec, None) == 0
    assert "adapter_type=e1000" in capsys.readouterr().out


def test_verify_detecta_nodo_no_arrancado(monkeypatch, capsys):
    def falso(argv, server=None):
        if argv[0] == "status":
            return 0, (
                " * lab-ejemplo                      abierto  abcd1234\n"
                "      pc1              vpcs             stopped   telnet:5000\n"
                "      pc2              vpcs             started   telnet:5001\n"
                "      sw1              ethernet_switch  started   telnet:5002\n")
        if argv[:2] == ["link", "list"]:
            return 0, ("  aaaaaaaa  pc1:0/0 <-> sw1:0/0\n"
                       "  bbbbbbbb  pc2:0/0 <-> sw1:1/0\n")
        return 0, ""

    monkeypatch.setattr(labspec, "capturar", falso)
    assert labspec.main(["verify", str(EJEMPLO)]) == 1
    salida = capsys.readouterr().out
    assert "pc1" in salida and "stopped" in salida
    assert "RESULTADO: FALLO" in salida


def test_verify_detecta_enlace_ausente(monkeypatch, capsys):
    def falso(argv, server=None):
        if argv[0] == "status":
            return 0, (
                " * lab-ejemplo                      abierto  abcd1234\n"
                "      pc1              vpcs             started   telnet:5000\n"
                "      pc2              vpcs             started   telnet:5001\n"
                "      sw1              ethernet_switch  started   telnet:5002\n")
        if argv[:2] == ["link", "list"]:
            return 0, "  aaaaaaaa  pc1:0/0 <-> sw1:0/0\n"
        return 0, ""

    monkeypatch.setattr(labspec, "capturar", falso)
    assert labspec.main(["verify", str(EJEMPLO)]) == 1
    assert "pc2" in capsys.readouterr().out


@pytest.mark.parametrize("accion", ["validate", "plan", "apply", "verify"])
def test_fichero_inexistente_no_revienta(tmp_path, accion):
    argv = [accion, str(tmp_path / "no.yaml")]
    if accion == "apply":
        argv.insert(1, "--yes")
    assert labspec.main(argv) == 1
