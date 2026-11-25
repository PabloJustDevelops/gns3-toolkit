"""Regresiones de gk8-hardening: config con `%`, resolución de ids y temporales."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from argparse import Namespace
from importlib.machinery import SourceFileLoader
from pathlib import Path

import gns3_mcp_server as server

CLI_PATH = Path(__file__).resolve().parents[1] / "cli" / "gns3lab"
LOADER = SourceFileLoader("gns3lab_hardeningtests", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)

COMPLETED = subprocess.CompletedProcess


# ───────────────────── 1. contraseña con `%` en la config ─────────────────────
def test_conf_lee_password_con_porcentaje_sin_interpolar(tmp_path, monkeypatch, capsys):
    conf = tmp_path / "gns3_server.conf"
    conf.write_text("[Server]\nhost = 127.0.0.1\nport = 3080\n"
                    "user = admin\npassword = ab%cd\n", encoding="utf-8")
    monkeypatch.setattr(server, "CONF", conf)
    monkeypatch.delenv("GNS3_PASSWORD", raising=False)
    monkeypatch.delenv("GNS3_USER", raising=False)

    assert server._conf()["password"] == "ab%cd"
    assert "ab%cd" not in capsys.readouterr().out


# ────────────── 2. nombre exacto antes que prefijo de id ambiguo ──────────────
def test_resolve_id_prefiere_el_nombre_exacto_al_prefijo_ambiguo():
    items = [
        {"node_id": "abcd-0001", "name": "R1"},
        {"node_id": "abcd-0002", "name": "SW1"},
        {"node_id": "ffff-0003", "name": "abcd"},
    ]

    assert cli._resolve_id(items, "abcd", "node_id", "nodo")["node_id"] == "ffff-0003"


# ─────────────────── 3. temporales únicos y sin fugas ────────────────────────
class _FakeUploadClient:
    def __init__(self, name: str):
        self.name = name

    def compute_write_file(self, *_args):
        return 200, {}

    def qemu_images(self):
        return [{"filename": self.name}]


def _fake_qemu(monkeypatch, module, rutas, returncode=0):
    """Sustituye qemu-img por una escritura en la ruta de destino que registra."""

    def fake_run(cmd, **_kwargs):
        destino = Path(cmd[-1])
        rutas.append(destino)
        destino.write_bytes(b"convertido")
        return COMPLETED(cmd, returncode, "", "" if returncode == 0 else "boom")

    monkeypatch.setattr(module.shutil, "which", lambda _nombre: "/usr/bin/qemu-img")
    monkeypatch.setattr(module.subprocess, "run", fake_run)


def test_gns3_upload_usa_dos_temporales_distintos_y_los_borra(tmp_path, monkeypatch):
    src = tmp_path / "disco.qcow2"
    src.write_bytes(b"original")
    rutas: list[Path] = []
    _fake_qemu(monkeypatch, server, rutas)
    monkeypatch.setattr(server, "_client",
                        lambda: _FakeUploadClient("disco.qcow2"))

    for _ in range(2):
        assert "error" not in server.gns3_upload(str(src), compress=True)

    assert len(rutas) == 2
    assert rutas[0] != rutas[1]
    assert all(not p.exists() for p in rutas)


def test_gns3_upload_borra_el_temporal_si_la_conversion_falla(tmp_path, monkeypatch):
    src = tmp_path / "disco.qcow2"
    src.write_bytes(b"original")
    rutas: list[Path] = []
    _fake_qemu(monkeypatch, server, rutas, returncode=1)
    monkeypatch.setattr(server, "_client",
                        lambda: _FakeUploadClient("disco.qcow2"))

    assert "error" not in server.gns3_upload(str(src), compress=True)

    assert len(rutas) == 1
    assert not rutas[0].exists()


def test_cmd_upload_usa_dos_temporales_distintos_y_los_borra(tmp_path, monkeypatch, capsys):
    src = tmp_path / "disco.qcow2"
    src.write_bytes(b"original")
    rutas: list[Path] = []
    _fake_qemu(monkeypatch, cli, rutas)
    monkeypatch.setattr(cli, "Server", lambda *_a, **_k: object())
    monkeypatch.setattr(cli, "_core_client",
                        lambda _s: _FakeUploadClient("disco.qcow2"))

    for _ in range(2):
        args = Namespace(server="local", file=str(src), name=None, compress=True)
        assert cli.cmd_upload(args, {}) == 0

    assert len(rutas) == 2
    assert rutas[0] != rutas[1]
    assert all(not p.exists() for p in rutas)
    capsys.readouterr()
