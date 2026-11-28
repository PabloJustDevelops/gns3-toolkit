"""`gns3lab exec` contra la API y la consola telnet falsas (#37)."""
from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

CLI_PATH = Path(__file__).resolve().parents[1] / "cli" / "gns3lab"
LOADER = SourceFileLoader("gns3lab_exectests", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)

pytestmark = pytest.mark.skipif(
    getattr(cli, "core", None) is None,
    reason="falta gns3core: la CLI no puede abrir la consola",
)

PFSENSE_PROMPT = b"[2.7.2-RELEASE][root@pfSense.home.arpa]/root: "


def _conf(url: str) -> dict:
    return {
        "servers": {"local": {"url": url, "auth": None}},
        "default_server": "local",
    }


def _api_con_nodo(fake_api, puerto: int) -> None:
    fake_api.set_projects([{"project_id": "p1", "name": "examen",
                            "status": "opened"}])
    fake_api.route("GET", "/v2/projects/p1", 200,
                   {"project_id": "p1", "status": "opened"})
    fake_api.set_nodes("p1", [{
        "node_id": "n1", "name": "PF1", "status": "started",
        "console": puerto, "console_type": "telnet", "console_host": "127.0.0.1",
    }])


def _args(**kw) -> Namespace:
    base = dict(server="local", node="PF1", commands=["uname -a"], project=None,
                ready_timeout=5, expect=None, idle=0.3, timeout=3, answers=[])
    base.update(kw)
    return Namespace(**base)


def test_exec_sincroniza_con_el_prompt_de_dos_puntos(telnet_factory, fake_api, capsys):
    """El prompt de pfSense termina en `:` y `exec` debe darlo por listo."""
    srv = telnet_factory(on_connect=PFSENSE_PROMPT,
                         on_line=lambda line: b"FreeBSD pfSense\r\n" + PFSENSE_PROMPT)
    _api_con_nodo(fake_api, srv.port)

    rc = cli.cmd_exec(_args(), _conf(fake_api.url))
    salida = capsys.readouterr()

    assert rc == 0
    assert "ready=True" in salida.err, salida.err
    assert "/root:" in salida.err, salida.err
    assert "FreeBSD pfSense" in salida.out


def test_exec_pasa_el_expect_a_wait_ready(telnet_factory, fake_api, capsys):
    """`--expect` cierra también la sincronización, no solo la lectura."""
    srv = telnet_factory(on_connect=PFSENSE_PROMPT,
                         on_line=lambda line: b"READY-MARK\r\n" + PFSENSE_PROMPT)
    _api_con_nodo(fake_api, srv.port)

    rc = cli.cmd_exec(_args(expect="READY-MARK"), _conf(fake_api.url))
    salida = capsys.readouterr()

    assert rc == 0
    assert "prompt='READY-MARK'" in salida.err, salida.err
    assert "ready=True" in salida.err, salida.err
