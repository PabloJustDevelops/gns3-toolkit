"""Aviso de versiones nuevas por CLI: sin red real ni reloj real.

El módulo de la CLI se carga igual que en `test_cli_json.py`; `urlopen`, el
reloj y el directorio de caché se sustituyen por dobles.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import urllib.error
import urllib.request
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

import pytest

CLI_PATH = Path(__file__).resolve().parents[1] / "cli" / "gns3lab"
LOADER = SourceFileLoader("gns3lab_update_extests", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)

RELEASES = "https://api.github.com/repos/PabloJustDevelops/gns3-toolkit/releases/latest"
TAGS = "https://api.github.com/repos/PabloJustDevelops/gns3-toolkit/tags"
NOW = 1_700_000_000.0


class Respuesta:
    """Respuesta mínima que usan como context manager las llamadas a urlopen."""

    def __init__(self, payload):
        self._data = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._data


class UrlopenFalso:
    """Responde por URL; una excepción en el mapa se eleva tal cual."""

    def __init__(self, rutas: dict):
        self.rutas = rutas
        self.llamadas: list[tuple[str, float | None]] = []

    def __call__(self, req, timeout=None):
        url = getattr(req, "full_url", str(req))
        self.llamadas.append((url, timeout))
        valor = self.rutas.get(url)
        if isinstance(valor, Exception):
            raise valor
        if valor is None:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        return Respuesta(valor)


@pytest.fixture(autouse=True)
def aislado(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.delenv("GNS3LAB_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(cli, "_now", lambda: NOW)

    def sin_red(*_a, **_k):
        raise AssertionError("el test intentó salir a la red")

    monkeypatch.setattr(urllib.request, "urlopen", sin_red)
    return tmp_path


def _cache(epoch: float, **extra) -> Path:
    ruta = cli._cache_file()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    datos = {"epoch": epoch, "installed": "0.0.1", "latest": "0.0.2",
             "update_available": True, "source": "releases",
             "checked_at": "2023-11-14T22:13:20+00:00", "error": None}
    datos.update(extra)
    ruta.write_text(json.dumps(datos))
    return ruta


def test_version_local_sale_de_version_file():
    assert cli.local_version() == "0.1.0"


def test_release_disponible(monkeypatch):
    fake = UrlopenFalso({RELEASES: {"tag_name": "v0.2.0"}})
    monkeypatch.setattr(urllib.request, "urlopen", fake)

    datos = cli.check_updates()

    assert datos["installed"] == "0.1.0"
    assert datos["latest"] == "0.2.0"
    assert datos["update_available"] is True
    assert datos["source"] == "releases"
    assert datos["error"] is None
    assert fake.llamadas[0][1] == 3


def test_404_en_releases_cae_a_tags(monkeypatch):
    fake = UrlopenFalso({
        TAGS: [{"name": "v0.2.10"}, {"name": "v0.3.0"}, {"name": "no-version"}],
    })
    monkeypatch.setattr(urllib.request, "urlopen", fake)

    datos = cli.check_updates()

    assert datos["latest"] == "0.3.0"
    assert datos["source"] == "tags"
    assert datos["update_available"] is True
    assert [url for url, _ in fake.llamadas] == [RELEASES, TAGS]


def test_sin_versiones_publicadas(monkeypatch):
    fake = UrlopenFalso({TAGS: []})
    monkeypatch.setattr(urllib.request, "urlopen", fake)

    datos = cli.check_updates()

    assert datos["latest"] is None
    assert datos["update_available"] is False
    assert datos["error"] is None
    assert "sin tags" in (datos.get("note") or "").lower()


@pytest.mark.parametrize(("instalada", "publicada", "esperado"), [
    ("0.1.0", "v0.1.0", False),
    ("0.1.0", "v0.0.9", False),
    ("0.9.0", "v0.10.0", True),   # léxicamente sería menor; numéricamente es mayor
])
def test_comparacion_numerica(monkeypatch, instalada, publicada, esperado):
    monkeypatch.setattr(cli, "local_version", lambda: instalada)
    fake = UrlopenFalso({RELEASES: {"tag_name": publicada}})
    monkeypatch.setattr(urllib.request, "urlopen", fake)

    assert cli.check_updates()["update_available"] is esperado


def test_cache_fresca_no_consulta_la_red(monkeypatch):
    _cache(NOW - 60, latest="9.9.9", update_available=True)

    datos = cli.check_updates()

    assert datos["latest"] == "9.9.9"
    assert datos["update_available"] is True
    assert datos["source"] == "releases"


def test_cache_caducada_vuelve_a_consultar(monkeypatch):
    _cache(NOW - cli.UPDATE_TTL - 1, latest="9.9.9")
    fake = UrlopenFalso({RELEASES: {"tag_name": "v0.2.0"}})
    monkeypatch.setattr(urllib.request, "urlopen", fake)

    datos = cli.check_updates()

    assert datos["latest"] == "0.2.0"
    assert len(fake.llamadas) == 1


def test_error_de_red_es_no_bloqueante(monkeypatch):
    fake = UrlopenFalso({RELEASES: urllib.error.URLError("sin ruta al host")})
    monkeypatch.setattr(urllib.request, "urlopen", fake)

    datos = cli.check_updates()

    assert datos["latest"] is None
    assert datos["update_available"] is False
    assert datos["error"]
    assert "sin ruta al host" in datos["error"]
    json.dumps(datos)  # serializable, sin traceback


def test_env_desactiva_la_red_sin_cache(monkeypatch):
    monkeypatch.setenv("GNS3LAB_NO_UPDATE_CHECK", "1")

    datos = cli.check_updates()

    assert datos["latest"] is None
    assert datos["update_available"] is False
    assert datos["error"] is None
    assert "sin comprobaci" in (datos.get("note") or "").lower()


def test_env_desactiva_la_red_pero_usa_cache(monkeypatch):
    monkeypatch.setenv("GNS3LAB_NO_UPDATE_CHECK", "1")
    _cache(NOW - cli.UPDATE_TTL - 1, latest="0.4.0")

    datos = cli.check_updates()

    assert datos["latest"] == "0.4.0"


def test_doctor_json_incluye_objeto_updates(monkeypatch, capsys):
    class ServidorFalso:
        name = "local"
        url = "http://127.0.0.1:1"

        def __init__(self, *_a, **_k):
            pass

        def alive(self):
            return False

    monkeypatch.setattr(cli, "Server", ServidorFalso)
    monkeypatch.setattr(cli, "check_updates", lambda: {
        "installed": "0.1.0", "latest": "0.2.0", "update_available": True,
        "source": "releases", "checked_at": "2023-11-14T22:13:20+00:00",
        "error": None,
    })
    args = SimpleNamespace(server="local", project=None, json=True,
                           check_updates=True)

    rc = cli.cmd_doctor(args, {})

    salida = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert salida["updates"] == {
        "installed": "0.1.0", "latest": "0.2.0", "update_available": True,
        "source": "releases", "checked_at": "2023-11-14T22:13:20+00:00",
        "error": None,
    }
