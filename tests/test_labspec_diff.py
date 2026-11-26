"""Contrato de export, diff y apply idempotente del laboratorio declarativo."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import labspec  # noqa: E402  (módulo sin dependencias del servidor)

requires_export = pytest.mark.skipif(
    not hasattr(labspec, "export"),
    reason="BRIEF-dclcore pendiente: falta export(topology)",
)
requires_diff_plan = pytest.mark.skipif(
    not all(hasattr(labspec, nombre) for nombre in ("diff", "plan")),
    reason="BRIEF-dclcore pendiente: faltan diff(deseado, actual) y plan",
)
requires_aplicar_deseado = pytest.mark.skipif(
    not hasattr(labspec, "aplicar_deseado"),
    reason="BRIEF-dclcore pendiente: falta aplicar_deseado(deseado, actual, server, yes)",
)


def _spec(nodes, links=()) -> dict:
    return {
        "version": 1,
        "project": "p",
        "nodes": list(nodes),
        "links": list(links),
        "expect": {},
    }


@requires_export
def test_export_valido_omite_enlaces_rotos_y_no_inventa_ip_ni_expect():
    topologia = {
        "project": "p",
        "nodes": [
            {
                "name": "pc1",
                "node_type": "vpcs",
                "properties": {"adapter_type": "e1000"},
            },
            {"name": "sw1", "template": "Ethernet switch", "properties": {}},
        ],
        "links": [
            {"ends": [
                {"node": "pc1", "adapter": 0},
                {"node": "sw1", "adapter": 1},
            ]},
            {"ends": [{"node": "pc1", "adapter": 1}]},
        ],
    }

    especificacion = labspec.export(topologia)

    assert labspec.validar(especificacion) == []
    assert especificacion["nodes"] == [
        {"name": "pc1", "template": "vpcs", "adapter_type": "e1000"},
        {"name": "sw1", "template": "Ethernet switch"},
    ]
    assert especificacion["links"] == [
        {"a": "pc1", "b": "sw1", "pa": 0, "pb": 1},
    ]
    assert all("ip" not in nodo for nodo in especificacion["nodes"])
    assert especificacion.get("expect", {}) == {}
    assert especificacion.get("warn")
    assert "links[1]" in str(especificacion["warn"])


@requires_export
@requires_diff_plan
def test_export_diff_y_plan_conservan_los_puertos_del_enlace():
    topologia = {
        "project": "p",
        "nodes": [
            {"name": "pc1", "node_type": "VPCS"},
            {"name": "sw1", "node_type": "ethernet_switch"},
        ],
        "links": [{"ends": [
            {"node": "pc1", "adapter": 0, "port_number": 2},
            {"node": "sw1", "adapter": 1, "port_number": 3},
        ]}],
    }

    deseado = labspec.export(topologia)
    enlace = {"a": "pc1", "b": "sw1", "pa": 0, "pb": 1,
              "porta": 2, "portb": 3}

    assert labspec.validar(deseado) == []
    assert deseado["links"] == [enlace]
    actual = _spec(
        [{"name": "pc1", "template": "VPCS"},
         {"name": "sw1", "template": "ethernet_switch"}],
        [{"a": "pc1", "b": "sw1", "pa": 0, "pb": 1}],
    )
    resultado = labspec.diff(deseado, actual)
    assert resultado["crear_enlaces"] == [enlace]
    assert resultado["sobrantes_enlaces"] == actual["links"]
    assert labspec.plan(deseado, actual) == [[
        "link", "add", "pc1", "sw1", "--pa", "0", "--pb", "1",
        "--ppa", "2", "--ppb", "3", "-p", "p",
    ]]


@requires_diff_plan
def test_diff_detecta_nodos_y_enlaces_nuevos_y_sobrantes():
    deseado = _spec(
        [
            {"name": "pc1", "template": "VPCS", "adapter_type": "e1000"},
            {"name": "sw1", "template": "Ethernet switch", "adapter_type": "e1000"},
        ],
        [{"a": "pc1", "b": "sw1", "pa": 0, "pb": 1}],
    )
    actual = _spec(
        [
            {"name": "pc1", "template": "VPCS", "adapter_type": "e1000"},
            {"name": "viejo", "template": "VPCS"},
        ],
        [{"a": "pc1", "b": "viejo", "pa": 2, "pb": 3}],
    )

    resultado = labspec.diff(deseado, actual)

    assert resultado["crear_nodos"] == [
        {"name": "sw1", "template": "Ethernet switch", "adapter_type": "e1000"},
    ]
    assert resultado["crear_enlaces"] == [
        {"a": "pc1", "b": "sw1", "pa": 0, "pb": 1},
    ]
    assert resultado["sobrantes_nodos"] == ["viejo"]
    assert resultado["sobrantes_enlaces"] == [
        {"a": "pc1", "b": "viejo", "pa": 2, "pb": 3},
    ]
    assert resultado["sin_cambios"] is False


@requires_diff_plan
def test_diff_y_plan_son_idempotentes():
    especificacion = _spec(
        [
            {"name": "pc1", "template": "VPCS"},
            {"name": "pc2", "template": "VPCS"},
        ],
        [{"a": "pc1", "b": "pc2", "pa": 0, "pb": 0}],
    )

    assert labspec.diff(especificacion, especificacion)["sin_cambios"] is True
    assert labspec.plan(especificacion, especificacion) == []


@requires_diff_plan
def test_plan_solo_arranca_al_crear_el_proyecto():
    deseado = _spec([{"name": "pc1", "template": "VPCS"}])
    existente = _spec([])
    nodo = ["node", "add", "--template", "VPCS", "--name", "pc1", "-p", "p"]

    assert labspec.plan(deseado, existente) == [nodo]
    assert labspec.plan(deseado, {}) == [["new", "p"], nodo, ["up", "p"]]


@requires_aplicar_deseado
def test_aplicar_deseado_sin_yes_no_ejecuta(monkeypatch):
    def prohibido(*_args, **_kwargs):
        raise AssertionError("sin --yes no se debe ejecutar ninguna orden")

    monkeypatch.setattr(labspec, "ejecutar", prohibido)

    assert labspec.aplicar_deseado(
        _spec([{"name": "pc1", "template": "VPCS"}]), {}, "local", False
    ) == 2


@requires_aplicar_deseado
@requires_diff_plan
def test_aplicar_deseado_con_yes_ejecuta_el_plan_en_orden(monkeypatch):
    deseado = _spec(
        [
            {"name": "pc1", "template": "VPCS"},
            {"name": "pc2", "template": "VPCS"},
        ],
        [{"a": "pc1", "b": "pc2", "pa": 0, "pb": 0}],
    )
    actual = {}
    llamadas = []

    def ejecutar(argv, server=None):
        llamadas.append((list(argv), server))
        return 0

    monkeypatch.setattr(labspec, "ejecutar", ejecutar)

    assert labspec.aplicar_deseado(deseado, actual, "local", True) == 0
    assert llamadas == [
        (["new", "p"], "local"),
        (["node", "add", "--template", "VPCS", "--name", "pc1", "-p", "p"], "local"),
        (["node", "add", "--template", "VPCS", "--name", "pc2", "-p", "p"], "local"),
        (["link", "add", "pc1", "pc2", "--pa", "0", "--pb", "0", "-p", "p"], "local"),
        (["up", "p"], "local"),
    ]


@requires_aplicar_deseado
@requires_diff_plan
def test_aplicar_deseado_con_yes_para_en_el_primer_fallo(monkeypatch):
    deseado = _spec(
        [
            {"name": "pc1", "template": "VPCS"},
            {"name": "pc2", "template": "VPCS"},
        ],
        [{"a": "pc1", "b": "pc2", "pa": 0, "pb": 0}],
    )
    actual = _spec([])
    llamadas = []

    def ejecutar(argv, server=None):
        llamadas.append(list(argv))
        return 9 if len(llamadas) == 2 else 0

    monkeypatch.setattr(labspec, "ejecutar", ejecutar)

    assert labspec.aplicar_deseado(deseado, actual, None, True) == 9
    assert llamadas == [
        ["node", "add", "--template", "VPCS", "--name", "pc1", "-p", "p"],
        ["node", "add", "--template", "VPCS", "--name", "pc2", "-p", "p"],
    ]
