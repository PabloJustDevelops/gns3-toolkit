"""Capturas por fase sobre HMP: contrato de captures.py y su uso desde labspec."""
from __future__ import annotations

import builtins
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import captures  # noqa: E402
import labspec  # noqa: E402

PPM = b"P6\n2 2\n255\n" + bytes((
    0, 0, 0, 255, 255, 255,
    255, 0, 0, 0, 255, 0,
))


class MonitorFalso:
    def __init__(self, error=None):
        self.error = error
        self.dest = None
        self.scale = None
        self.cerrado = False

    def screendump(self, dest=None, scale=0):
        self.dest = Path(dest) if dest else None
        self.scale = scale
        if self.error:
            return {"error": self.error}
        self.dest.write_bytes(PPM)
        return {"path": str(self.dest), "size": (2, 2), "bytes": len(PPM)}

    def close(self):
        self.cerrado = True


def _sin_pillow(monkeypatch):
    import_original = builtins.__import__

    def importar(nombre, *args, **kwargs):
        if nombre == "PIL" or nombre.startswith("PIL."):
            raise ImportError("No module named 'PIL'")
        return import_original(nombre, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", importar)


def _spec_con_capturas(after="apply"):
    return {
        "version": 1,
        "project": "p",
        "nodes": [{"name": "PF1", "template": "pfSense"}],
        "links": [],
        "expect": {},
        "captures": [{"phase": "topologia", "after": after, "node": "PF1"}],
    }


def test_capture_phase_convierte_ppm_a_png_y_usa_ocr_x2_psm4(monkeypatch, tmp_path):
    (tmp_path / "03-viejo.png").write_bytes(b"previo")
    monitor = MonitorFalso()
    argumentos = []

    def ocr_falso(path, psm=6):
        argumentos.append((path, psm))
        return "Show interfaces"

    monkeypatch.setattr(captures, "ocr", ocr_falso)
    monkeypatch.setattr(captures.shutil, "which", lambda nombre: "/usr/bin/tesseract")

    resultado = captures.capture_phase(monitor, "topologia", str(tmp_path), "PF1")

    assert set(resultado) == {"ok", "phase", "path", "ocr", "node", "error"}
    assert resultado["ok"] is True
    assert resultado["phase"] == "topologia"
    assert resultado["node"] == "PF1"
    assert resultado["error"] is None
    assert resultado["ocr"] == "Show interfaces"
    assert resultado["path"] == str(tmp_path / "04-topologia.png")
    assert Path(resultado["path"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert monitor.scale == 2
    assert argumentos == [(resultado["path"], 4)]
    assert monitor.dest is not None and not monitor.dest.parent.exists()


def test_capture_phase_no_sobrescribe_fases_con_saltos_de_linea(monkeypatch, tmp_path):
    monkeypatch.setattr(captures, "ocr", lambda path, psm=4: "texto")
    monkeypatch.setattr(captures.shutil, "which", lambda nombre: "/usr/bin/tesseract")
    fase = "fase\nsalto"

    primero = captures.capture_phase(MonitorFalso(), fase, str(tmp_path))
    assert primero["path"] == str(tmp_path / f"01-{fase}.png")
    Path(primero["path"]).write_bytes(b"primero")

    segundo = captures.capture_phase(MonitorFalso(), fase, str(tmp_path))

    assert segundo["path"] == str(tmp_path / f"02-{fase}.png")
    assert Path(primero["path"]).read_bytes() == b"primero"


def test_capture_phase_sin_pillow_conserva_ppm_y_lo_reporta(monkeypatch, tmp_path):
    _sin_pillow(monkeypatch)
    monkeypatch.setattr(captures, "ocr", lambda path, psm=4: "texto")
    monkeypatch.setattr(captures.shutil, "which", lambda nombre: "/usr/bin/tesseract")

    resultado = captures.capture_phase(MonitorFalso(), "consola", str(tmp_path))

    assert resultado["ok"] is True
    assert resultado["path"] == str(tmp_path / "01-consola.ppm")
    assert Path(resultado["path"]).read_bytes() == PPM
    assert resultado["ocr"] == "texto"
    assert "Pillow" in resultado["error"]


def test_capture_phase_sin_tesseract_degrada_ocr_y_lo_reporta(monkeypatch, tmp_path):
    monkeypatch.setattr(captures.shutil, "which", lambda nombre: None)
    monkeypatch.setattr(captures, "ocr", lambda path, psm=4: "")

    resultado = captures.capture_phase(MonitorFalso(), "verificacion", str(tmp_path))

    assert resultado["ok"] is True
    assert resultado["ocr"] == ""
    assert "tesseract" in resultado["error"].lower()
    assert Path(resultado["path"]).is_file()


def test_capture_phase_propaga_error_de_screendump_sin_lanzar(tmp_path):
    resultado = captures.capture_phase(
        MonitorFalso("screendump no generó fichero"), "topologia", str(tmp_path)
    )

    assert resultado["ok"] is False
    assert resultado["path"] is None
    assert resultado["ocr"] == ""
    assert "screendump no generó fichero" in resultado["error"]


def test_write_index_con_tres_fases_recorta_ocr_y_resume_estado(tmp_path):
    entradas = [
        {"phase": "topologia", "path": str(tmp_path / "01-topologia.png"),
         "node": "PF1", "ocr": "linea uno | linea dos\n" + "x" * 300, "ok": True},
        {"phase": "reglas", "path": str(tmp_path / "02-reglas.png"),
         "node": None, "ocr": "", "ok": False, "error": "sin monitor"},
        {"phase": "verificacion", "path": str(tmp_path / "03-verificacion.png"),
         "node": "PC1", "ocr": "0% packet loss", "ok": True},
    ]

    ruta = captures.write_index(entradas, str(tmp_path))
    texto = Path(ruta).read_text(encoding="utf-8")

    assert ruta == str(tmp_path / "indice.md")
    assert "| fase | archivo | nodo | OCR |" in texto
    assert "01-topologia.png" in texto
    assert "02-reglas.png" in texto
    assert "PF1" in texto and "PC1" in texto
    assert "0% packet loss" in texto
    assert "linea uno" in texto and "línea dos" not in texto
    assert "…" in texto
    assert "Estado: 2 OK, 1 fallo" in texto
    assert len([linea for linea in texto.splitlines() if linea.startswith("| ")]) == 4


def test_phases_from_spec_es_opcional_y_normaliza_como_maximo_cinco():
    assert captures.phases_from_spec({}) == []
    especificacion = {"captures": [
        {"phase": f"fase{i}", "after": "apply" if i % 2 == 0 else "verify"}
        for i in range(5)
    ]}

    fases = captures.phases_from_spec(especificacion)

    assert len(fases) == 5
    assert fases[0] == {"phase": "fase0", "after": "apply", "node": None}
    assert fases[-1]["after"] == "apply"


def test_phases_from_spec_rechaza_mas_de_cinco_con_ruta():
    especificacion = {"captures": [
        {"phase": f"fase{i}", "after": "apply"} for i in range(6)
    ]}

    with pytest.raises(ValueError, match=r"captures: máximo 5 fases"):
        captures.phases_from_spec(especificacion)


@pytest.mark.parametrize("entrada,ruta", [
    ({"after": "apply"}, "captures[0].phase"),
    ({"phase": "topologia", "after": "despues"}, "captures[0].after"),
    ({"phase": "topologia", "after": []}, "captures[0].after"),
    ({"phase": "topologia", "after": {}}, "captures[0].after"),
])
def test_phases_from_spec_informa_la_ruta_del_campo(entrada, ruta):
    with pytest.raises(ValueError, match=ruta.replace("[", r"\[").replace("]", r"\]")):
        captures.phases_from_spec({"captures": [entrada]})


def test_fallo_de_captura_no_cambia_exit_de_aplicar_deseado(monkeypatch, tmp_path, capsys):
    especificacion = _spec_con_capturas()
    monitor = MonitorFalso()
    llamadas = []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(labspec, "ejecutar", lambda argv, server=None: 0)
    monkeypatch.setattr(labspec, "_monitor_captura", lambda *args: monitor)

    def capturar(mon, phase, outdir, node=None):
        llamadas.append((phase, outdir, node))
        return {"ok": False, "phase": phase, "path": None, "ocr": "",
                "node": node, "error": "fallo simulado de captura"}

    monkeypatch.setattr(captures, "capture_phase", capturar)

    rc = labspec.aplicar_deseado(especificacion, {}, None, True, captures=True)

    assert rc == 0
    assert llamadas == [("topologia", str(Path.home() / "GNS3/captures/p"), "PF1")]
    assert monitor.cerrado is True
    salida = capsys.readouterr().out
    assert "FALLO" in salida
    assert "fallo simulado de captura" in salida


def test_aplicar_deseado_sin_captures_no_abre_monitor(monkeypatch):
    especificacion = _spec_con_capturas()

    def prohibido(*_args):
        raise AssertionError("captures=False no debe abrir un monitor")

    monkeypatch.setattr(labspec, "ejecutar", lambda argv, server=None: 0)
    monkeypatch.setattr(labspec, "_monitor_captura", prohibido)

    assert labspec.aplicar_deseado(especificacion, {}, None, True) == 0


def test_capture_phase_acepta_la_conversion_ya_hecha_por_screendump(monkeypatch, tmp_path):
    class MonitorComoQemu:
        def screendump(self, dest=None, scale=0):
            from PIL import Image

            ppm = Path(dest).with_suffix(".ppm")
            ppm.write_bytes(PPM)
            with Image.open(ppm) as imagen:
                imagen.convert("L").save(dest)
            ppm.unlink()
            return {"path": dest, "size": (2, 2), "bytes": Path(dest).stat().st_size}

    monkeypatch.setattr(captures, "ocr", lambda path, psm=4: "Show status")
    monkeypatch.setattr(captures.shutil, "which", lambda nombre: "/usr/bin/tesseract")

    resultado = captures.capture_phase(MonitorComoQemu(), "estado", str(tmp_path))

    assert resultado["ok"] is True
    assert resultado["path"] == str(tmp_path / "01-estado.png")
    assert Path(resultado["path"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_labspec_valida_y_normaliza_el_bloque_captures():
    especificacion = _spec_con_capturas()

    assert labspec.validar(especificacion) == []
    assert labspec.normalizar(especificacion)["captures"] == [
        {"phase": "topologia", "after": "apply", "node": "PF1"}
    ]

    especificacion["captures"][0]["after"] = "despues"
    assert any("captures[0].after" in error for error in labspec.validar(especificacion))


@pytest.mark.parametrize("after", [[], {}])
def test_labspec_validar_after_no_texto_reporta_ruta(after):
    especificacion = _spec_con_capturas()
    especificacion["captures"][0]["after"] = after

    errores = labspec.validar(especificacion)

    assert any("captures[0].after" in error for error in errores)


def test_fallo_de_captura_no_cambia_exit_de_verificar(monkeypatch, capsys):
    especificacion = _spec_con_capturas(after="verify")
    eventos = []
    monitor = MonitorFalso()

    def capturar(argv, server=None):
        eventos.append(argv[0])
        if argv[0] == "status":
            return 0, (
                " * p abierto abcd1234\n"
                "      PF1 qemu started -:5000\n"
            )
        if argv[:2] == ["link", "list"]:
            return 0, ""
        raise AssertionError(f"orden inesperada: {argv}")

    def capturar_fase(mon, phase, outdir, node=None):
        eventos.append("capture")
        return {"ok": False, "phase": phase, "path": None, "ocr": "",
                "node": node, "error": "sin monitor HMP"}

    monkeypatch.setattr(labspec, "capturar", capturar)
    monkeypatch.setattr(labspec, "_monitor_captura", lambda *args: monitor)
    monkeypatch.setattr(captures, "capture_phase", capturar_fase)

    rc = labspec.verificar(especificacion, None, captures=True)

    assert rc == 0
    assert eventos[-2:] == ["link", "capture"]
    assert monitor.cerrado is True
    salida = capsys.readouterr().out
    assert "captura topologia: FALLO (sin monitor HMP)" in salida
    assert "RESULTADO: OK" in salida
