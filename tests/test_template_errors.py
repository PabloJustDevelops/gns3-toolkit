"""Un HTTP 500 al leer plantillas no debe parecerse a 'no hay plantillas'."""
from __future__ import annotations

import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CLI_PATH = REPO / "cli" / "gns3lab"
LOADER = SourceFileLoader("gns3lab_template_errors", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)


@pytest.mark.skipif(
    not hasattr(cli, "_templates_or_die"),
    reason="sin helper _templates_or_die: arreglo en esta rama",
)
def test_http_500_se_propaga_como_error_literal():
    class Cliente:
        def json_or_die(self, path, what):
            assert path == "/v2/templates"
            raise RuntimeError(f"{what}: [500] {{'detail': 'boom'}}")

    with pytest.raises(RuntimeError, match=r"plantillas: \[500\]"):
        cli._templates_or_die(Cliente())


@pytest.mark.skipif(
    not hasattr(cli, "_templates_or_die"),
    reason="sin helper _templates_or_die: arreglo en esta rama",
)
def test_respuesta_no_lista_no_se_leye_como_vacia():
    class Cliente:
        def json_or_die(self, _path, _what):
            return {"detail": "boom"}

    with pytest.raises(RuntimeError, match="respuesta no válida"):
        cli._templates_or_die(Cliente())


@pytest.mark.skipif(
    not hasattr(cli, "_templates_or_die"),
    reason="sin helper _templates_or_die: arreglo en esta rama",
)
def test_server_con_get_tambien_propaga_el_500():
    class Server:
        def get(self, path):
            assert path == "/v2/templates"
            return 500, {"detail": "boom"}

    with pytest.raises(RuntimeError, match=r"plantillas: \[500\]"):
        cli._templates_or_die(Server())


def test_unico_punto_de_lectura_de_plantillas():
    fuente = CLI_PATH.read_text(encoding="utf-8")
    assert "templates if isinstance(templates, list) else []" not in fuente
    assert ".templates()" not in fuente
    assert "def _templates_or_die" in fuente
