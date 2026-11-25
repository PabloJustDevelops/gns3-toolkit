"""`QemuMonitor`: teclas, `for_node`, `screendump` y las ramas de `_read`/`run`."""
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import gns3core
from gns3core import QemuMonitor

# PPM mínimo válido (P6, 32x32, rojo) como el que escribe `screendump` de QEMU.
# Supera los 1000 bytes a propósito: `screendump` espera a que el fichero crezca.
PPM = b"P6\n32 32\n255\n" + bytes([255, 0, 0] * (32 * 32))


def _esperar_comandos(srv, n, timeout=2.0):
    fin = time.time() + timeout
    while len(srv.commands) < n and time.time() < fin:
        time.sleep(0.01)
    return srv.commands


# ─────────────────────────────── sendkey ───────────────────────────────
def test_sendkey_manda_cada_tecla_y_devuelve_las_enviadas(hmp_factory):
    srv = hmp_factory()
    with QemuMonitor(srv.port) as mon:
        res = mon.sendkey("ret", "shift-2", delay=0)
        comandos = _esperar_comandos(srv, 2)

    assert res == {"sent": ["ret", "shift-2"]}
    assert comandos == ["sendkey ret", "sendkey shift-2"]


# ─────────────────────────────── for_node ───────────────────────────────
def test_for_node_falla_si_no_hay_monitor(monkeypatch):
    monkeypatch.setattr(gns3core, "find_monitor_port", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="no encuentro el monitor"):
        QemuMonitor.for_node(node_id="n1")


def test_for_node_usa_el_puerto_encontrado(hmp_factory, monkeypatch):
    srv = hmp_factory()
    monkeypatch.setattr(gns3core, "find_monitor_port", lambda *a, **k: srv.port)
    with QemuMonitor.for_node(node_id="n1") as mon:
        assert mon.run("info status")["output"] == "VM status: running"


# ────────────────────────────── _read / run ──────────────────────────────
def test_read_corta_con_eof(hmp_factory, stub_sock):
    mon = QemuMonitor(hmp_factory().port)
    mon.sock = stub_sock(recv=[b""])
    assert mon._read(0.1) == ""


def test_read_corta_con_oserror(hmp_factory, stub_sock):
    mon = QemuMonitor(hmp_factory().port)
    mon.sock = stub_sock(recv=[OSError("canal roto")])
    assert mon._read(0.1) == ""


def test_close_traga_el_oserror(hmp_factory, stub_sock):
    mon = QemuMonitor(hmp_factory().port)
    mon.sock = stub_sock(close_exc=OSError("ya cerrado"))
    mon.close()                       # no lanza


def test_run_espera_al_prompt_si_no_viene_en_el_primer_chunk(hmp_factory, stub_sock):
    mon = QemuMonitor(hmp_factory().port)
    mon.sock = stub_sock(recv=[
        b"",                                        # primera lectura sin nada
        b"\r\nVM status: running\r\n(qemu) ",       # llega en la siguiente
    ])
    res = mon.run("info status", timeout=2)
    assert res["output"] == "VM status: running"
    assert res["raw_len"] > 0


def test_run_rompe_si_el_canal_se_cierra_sin_prompt(hmp_factory, stub_sock):
    mon = QemuMonitor(hmp_factory().port)
    mon.sock = stub_sock(recv=[b"eco sin prompt\r\n", b""])
    res = mon.run("info status", timeout=2)
    assert res["cmd"] == "info status"


# ─────────────────────────────── screendump ───────────────────────────────
def _hmp_que_escribe_ppm(hmp_factory, ppm=PPM):
    """HMP falso cuyo `screendump <ruta>` escribe un PPM real en esa ruta."""
    srv = hmp_factory()

    def on_command(cmd):
        if cmd.startswith("screendump "):
            Path(cmd.split(" ", 1)[1]).write_bytes(ppm)
            return ""
        return f"Error: unknown command '{cmd}'"

    srv.on_command = on_command
    return srv


def test_screendump_con_pillow_convierte_y_escala(hmp_factory, tmp_path):
    srv = _hmp_que_escribe_ppm(hmp_factory)
    dest = tmp_path / "captura.png"
    dest.with_suffix(".ppm").write_bytes(b"PPM de una captura anterior")

    with QemuMonitor(srv.port) as mon:
        res = mon.screendump(dest=str(dest), scale=2)

    assert res["path"] == str(dest)
    assert res["size"] == (64, 64)                # 32x32 escalado x2
    assert res["bytes"] > 0
    assert dest.exists()
    assert not dest.with_suffix(".ppm").exists()  # el PPM intermedio se borra

    from PIL import Image
    with Image.open(dest) as img:
        assert img.mode == "L"
        assert img.size == (64, 64)


def test_screendump_sin_pillow_usa_magick(hmp_factory, tmp_path, monkeypatch):
    srv = _hmp_que_escribe_ppm(hmp_factory)
    dest = tmp_path / "captura.png"
    monkeypatch.setitem(sys.modules, "PIL", None)          # fuerza ImportError
    monkeypatch.setattr(gns3core.shutil, "which",
                        lambda name: "/usr/bin/magick" if name == "magick" else None)

    def fake_run(argv, **_kw):
        Path(argv[2]).write_bytes(b"PNG de magick")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(gns3core.subprocess, "run", fake_run)
    with QemuMonitor(srv.port) as mon:
        res = mon.screendump(dest=str(dest))

    assert res["converted_by"] == "magick"
    assert res["size"] is None
    assert Path(res["path"]).read_bytes() == b"PNG de magick"
    assert not dest.with_suffix(".ppm").exists()


def test_screendump_sin_pillow_ni_convertidor_deja_el_ppm(hmp_factory, tmp_path,
                                                          monkeypatch):
    srv = _hmp_que_escribe_ppm(hmp_factory)
    dest = tmp_path / "captura.png"
    monkeypatch.setitem(sys.modules, "PIL", None)
    monkeypatch.setattr(gns3core.shutil, "which", lambda name: None)

    with QemuMonitor(srv.port) as mon:
        res = mon.screendump(dest=str(dest))

    assert res["path"] == str(dest.with_suffix(".ppm"))
    assert res["size"] is None
    assert Path(res["path"]).exists()


def test_screendump_con_convertidor_que_falla_deja_el_ppm(hmp_factory, tmp_path,
                                                          monkeypatch):
    srv = _hmp_que_escribe_ppm(hmp_factory)
    dest = tmp_path / "captura.png"
    monkeypatch.setitem(sys.modules, "PIL", None)
    monkeypatch.setattr(gns3core.shutil, "which",
                        lambda name: "/usr/bin/convert" if name == "convert" else None)
    monkeypatch.setattr(gns3core.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=1))

    with QemuMonitor(srv.port) as mon:
        res = mon.screendump(dest=str(dest))

    assert res["path"] == str(dest.with_suffix(".ppm"))
    assert "converted_by" not in res


def test_screendump_sin_fichero_devuelve_error(hmp_factory, tmp_path):
    srv = hmp_factory()
    srv.responses["screendump /nada/que/hacer.ppm"] = "Error: open failed"
    dest = tmp_path / "captura.png"

    with QemuMonitor(srv.port) as mon:
        res = mon.screendump(dest=str(dest))

    assert res["error"] == "screendump no generó fichero"
    assert res["detail"]["cmd"].startswith("screendump ")


# ────────────────────────────────── ocr ──────────────────────────────────
def test_ocr_sin_tesseract_devuelve_cadena_vacia(monkeypatch):
    monkeypatch.setattr(gns3core.shutil, "which", lambda name: None)
    assert gns3core.ocr("/no/existe.png") == ""


def test_ocr_corrige_la_w_que_tesseract_lee_como_u(monkeypatch):
    monkeypatch.setattr(gns3core.shutil, "which", lambda name: "/usr/bin/tesseract")
    visto = {}

    def fake_run(argv, **_kw):
        visto["argv"] = argv
        return SimpleNamespace(stdout="Shou ip\nshou route\n")

    monkeypatch.setattr(gns3core.subprocess, "run", fake_run)
    assert gns3core.ocr("pantalla.png", psm=4) == "Show ip\nshow route"
    assert visto["argv"][:2] == ["tesseract", "pantalla.png"]
    assert visto["argv"][3:5] == ["--psm", "4"]


def test_ocr_traga_el_fallo_de_tesseract(monkeypatch):
    monkeypatch.setattr(gns3core.shutil, "which", lambda name: "/usr/bin/tesseract")

    def boom(*_a, **_k):
        raise OSError("tesseract no arranca")

    monkeypatch.setattr(gns3core.subprocess, "run", boom)
    assert gns3core.ocr("pantalla.png") == ""


# ─────────────────────────────── screen_text ───────────────────────────────
class MonitorFalso:
    def __init__(self, shot):
        self.shot = shot
        self.scale = None

    def screendump(self, scale=0):
        self.scale = scale
        return dict(self.shot)


def test_screen_text_propaga_el_error_del_screendump():
    mon = MonitorFalso({"error": "screendump no generó fichero"})
    assert gns3core.screen_text(mon) == {"error": "screendump no generó fichero"}
    assert mon.scale == 2


def test_screen_text_anade_el_ocr_de_la_captura(monkeypatch, tmp_path):
    mon = MonitorFalso({"path": str(tmp_path / "x.png"), "size": (4, 4), "bytes": 10})
    monkeypatch.setattr(gns3core, "ocr", lambda path, psm=6: f"OCR {psm}")
    res = gns3core.screen_text(mon, psm=4, scale=3)
    assert res["ocr"] == "OCR 4"
    assert mon.scale == 3
