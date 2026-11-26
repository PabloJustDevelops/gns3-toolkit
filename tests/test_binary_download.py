"""Descarga binaria desde el compute por su URL directa.

El controller resuelve la URL con ``GET /v2/computes/endpoint/{cid}/{emu}/{action}``
pero su proxy serializa el cuerpo como JSON y devuelve 500 con binario; por eso la
descarga va contra el endpoint del compute, no contra ``/v2/computes/{cid}/...``.

Todos los dobles son ``http.server`` locales en 127.0.0.1: ninguna petición sale
del equipo.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
import urllib.error
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

import gns3_mcp_server as server
import gns3core
from gns3core import Client, ComputeDownloadError

CID = "compute-remoto"
DIRECTO = "/v2/compute/projects/p/qemu/binaries"
PAYLOAD = b"\x00\x01binario-de-prueba\n" * 64


def _endpoint(fake_api, url: str) -> None:
    fake_api.route("GET", f"/v2/computes/endpoint/{CID}/qemu/binaries", 200,
                   {"endpoint": url})


# ───────────────────────────── éxito ─────────────────────────────
def test_download_escribe_fichero_y_devuelve_metadatos(fake_api, tmp_path):
    _endpoint(fake_api, fake_api.url + DIRECTO)
    fake_api.route("GET", DIRECTO, 200, PAYLOAD)
    out = tmp_path / "binaries.bin"

    res = Client(fake_api.url).compute_download(CID, "qemu", "binaries", out)

    assert res == {
        "path": str(out),
        "bytes": len(PAYLOAD),
        "sha256": hashlib.sha256(PAYLOAD).hexdigest(),
        "content_type": "application/octet-stream",
        "compute_id": CID,
    }
    assert out.read_bytes() == PAYLOAD
    # El temporal vive en el directorio de destino y no debe sobrevivir.
    assert [p.name for p in tmp_path.iterdir()] == ["binaries.bin"]


def test_download_resuelve_el_endpoint_antes_de_bajar(fake_api, tmp_path):
    _endpoint(fake_api, fake_api.url + DIRECTO)
    fake_api.route("GET", DIRECTO, 200, PAYLOAD)

    Client(fake_api.url).compute_download(CID, "qemu", "binaries", tmp_path / "x.bin")

    assert fake_api.last("GET", f"/v2/computes/endpoint/{CID}/qemu/binaries")
    assert fake_api.last("GET", DIRECTO)


def test_download_rechaza_sobrescribir_sin_force(fake_api, tmp_path):
    _endpoint(fake_api, fake_api.url + DIRECTO)
    out = tmp_path / "existe.bin"
    out.write_bytes(b"original")

    with pytest.raises(FileExistsError, match="force"):
        Client(fake_api.url).compute_download(CID, "qemu", "binaries", out)

    assert out.read_bytes() == b"original"
    assert [p.name for p in tmp_path.iterdir()] == ["existe.bin"]


def test_download_con_force_sobrescribe(fake_api, tmp_path):
    _endpoint(fake_api, fake_api.url + DIRECTO)
    fake_api.route("GET", DIRECTO, 200, PAYLOAD)
    out = tmp_path / "existe.bin"
    out.write_bytes(b"original")

    res = Client(fake_api.url).compute_download(CID, "qemu", "binaries", out, force=True)

    assert out.read_bytes() == PAYLOAD
    assert res["bytes"] == len(PAYLOAD)


# ───────────────────────────── errores de endpoint ─────────────────────────────
def test_download_endpoint_http_404(fake_api, tmp_path):
    fake_api.route("GET", f"/v2/computes/endpoint/{CID}/qemu/binaries", 404,
                   {"message": "compute not found"})

    with pytest.raises(ComputeDownloadError, match=r"\[404\].*compute not found"):
        Client(fake_api.url).compute_download(CID, "qemu", "binaries", tmp_path / "x.bin")


def test_download_endpoint_ausente(fake_api, tmp_path):
    fake_api.route("GET", f"/v2/computes/endpoint/{CID}/qemu/binaries", 200, {})

    with pytest.raises(ComputeDownloadError, match="no devolvió"):
        Client(fake_api.url).compute_download(CID, "qemu", "binaries", tmp_path / "x.bin")


def test_download_endpoint_no_es_http(fake_api, tmp_path):
    _endpoint(fake_api, "ftp://127.0.0.1/binarios")

    with pytest.raises(ComputeDownloadError, match="no devolvió"):
        Client(fake_api.url).compute_download(CID, "qemu", "binaries", tmp_path / "x.bin")


# ───────────────────────────── errores de descarga ─────────────────────────────
@pytest.mark.parametrize("status", [404, 500])
def test_download_http_no_2xx_limpia_el_temporal(fake_api, tmp_path, status):
    _endpoint(fake_api, fake_api.url + DIRECTO)
    fake_api.route("GET", DIRECTO, status, {"message": "sin binarios"})

    with pytest.raises(ComputeDownloadError, match=rf"HTTP {status}"):
        Client(fake_api.url).compute_download(CID, "qemu", "binaries", tmp_path / "x.bin")

    assert list(tmp_path.iterdir()) == []


def test_download_timeout_limpia_el_temporal(fake_api, tmp_path, monkeypatch):
    _endpoint(fake_api, fake_api.url + DIRECTO)

    def timeout(*_a, **_kw):
        raise TimeoutError("se agotó el tiempo")

    monkeypatch.setattr(gns3core, "_open_url", timeout)

    with pytest.raises(TimeoutError, match="tiempo"):
        Client(fake_api.url).compute_download(CID, "qemu", "binaries", tmp_path / "x.bin")

    assert list(tmp_path.iterdir()) == []


def test_download_timeout_de_urllib_se_traduce(fake_api, tmp_path, monkeypatch):
    _endpoint(fake_api, fake_api.url + DIRECTO)

    def timeout(*_a, **_kw):
        raise urllib.error.URLError(TimeoutError("agotado"))

    monkeypatch.setattr(gns3core, "_open_url", timeout)

    with pytest.raises(TimeoutError, match=r"agotó el tiempo \(60s\)"):
        Client(fake_api.url).compute_download(CID, "qemu", "binaries", tmp_path / "x.bin")

    assert list(tmp_path.iterdir()) == []


def test_download_no_filtra_credenciales_en_el_error(fake_api, tmp_path, monkeypatch):
    _endpoint(fake_api, "http://usuario:clave-secreta@127.0.0.1:9/bin")

    def unreachable(*_a, **_kw):
        raise urllib.error.URLError("caído")

    monkeypatch.setattr(gns3core, "_open_url", unreachable)

    with pytest.raises(ComputeDownloadError) as exc:
        Client(fake_api.url).compute_download(CID, "qemu", "binaries", tmp_path / "x.bin")

    assert "clave-secreta" not in str(exc.value)
    assert "127.0.0.1:9/bin" in str(exc.value)


def test_download_manda_la_auth_del_controller_al_compute(fake_api, tmp_path):
    _endpoint(fake_api, fake_api.url + DIRECTO)
    fake_api.route("GET", DIRECTO, 200, PAYLOAD)

    Client(fake_api.url, auth=("usuario", "clave")).compute_download(
        CID, "qemu", "binaries", tmp_path / "x.bin")

    assert "authorization" in fake_api.last("GET", DIRECTO)["headers"]


# ───────────────────────────── ruta de destino ─────────────────────────────
@pytest.mark.parametrize("caso", ["directorio", "sin-nombre", "padre-ausente"])
def test_download_ruta_de_destino_invalida(fake_api, tmp_path, caso):
    destino = {
        "directorio": str(tmp_path),
        "sin-nombre": str(tmp_path / "nuevo") + "/",
        "padre-ausente": str(tmp_path / "noexiste" / "x.bin"),
    }[caso]

    with pytest.raises(ValueError, match="destino"):
        Client(fake_api.url).compute_download(CID, "qemu", "binaries", destino)

    # La ruta se valida antes de hablar con el servidor.
    assert not any(fake_api.requests)


# ───────────────────────────── MCP ─────────────────────────────
def test_mcp_compute_download_escribe_y_devuelve_metadatos(fake_api, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_conf", lambda: {
        "url": fake_api.url, "user": "u", "password": "p"})
    _endpoint(fake_api, fake_api.url + DIRECTO)
    fake_api.route("GET", DIRECTO, 200, PAYLOAD)
    out = tmp_path / "desde-mcp.bin"

    res = server.gns3_compute_download(CID, "qemu", "binaries", str(out))

    assert res["bytes"] == len(PAYLOAD)
    assert res["sha256"] == hashlib.sha256(PAYLOAD).hexdigest()
    assert res["compute_id"] == CID
    assert out.read_bytes() == PAYLOAD


def test_mcp_compute_download_devuelve_error_accionable(tmp_path):
    res = server.gns3_compute_download(CID, "qemu", "binaries",
                                       str(tmp_path / "noexiste" / "x.bin"))
    assert "destino" in res["error"]


# ───────────────────────────── CLI ─────────────────────────────
LOADER = SourceFileLoader("gns3lab_download_extests",
                          str(Path(__file__).resolve().parents[1] / "cli" / "gns3lab"))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)


def _cli_args(out: Path, **extra) -> argparse.Namespace:
    base = dict(cid=CID, emulator_arg="qemu", remote_arg="binaries", emulator=None,
                remote_action=None, out=str(out), force=False, json=True, set=[])
    base.update(extra)
    return argparse.Namespace(**base)


def test_cli_compute_download_json(fake_api, tmp_path, capsys):
    _endpoint(fake_api, fake_api.url + DIRECTO)
    fake_api.route("GET", DIRECTO, 200, PAYLOAD)
    out = tmp_path / "desde-cli.bin"

    rc = cli._cmd_compute_action(None, Client(fake_api.url),
                                 _cli_args(out), "download")

    assert rc == 0
    salida = capsys.readouterr().out
    assert '"sha256"' in salida
    assert out.read_bytes() == PAYLOAD


def test_cli_compute_download_sin_out_no_adivina(fake_api):
    args = argparse.Namespace(cid=CID, emulator_arg="qemu", remote_arg="binaries",
                              emulator=None, remote_action=None, out=None, force=False,
                              json=False, set=[])

    with pytest.raises(SystemExit, match="--out"):
        cli._cmd_compute_action(None, Client(fake_api.url), args, "download")
