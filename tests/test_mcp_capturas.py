"""Contrato de `gns3_capturas`, sin GNS3 real ni credenciales reales."""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

import gns3_mcp_server as server


@pytest.fixture
def captures_module(monkeypatch):
    module = ModuleType("captures")
    module.calls = []
    phases = [{"phase": "topologia", "after": "apply", "node": None}]

    def phases_from_spec(spec):
        module.calls.append(("phases", spec))
        return phases

    def capture_phase(monitor, phase, outdir, node=None):
        module.calls.append(("console", monitor, phase, outdir, node))
        return {"ok": True, "phase": phase, "path": str(Path(outdir) / "01-topologia.png"),
                "ocr": "pfSense", "node": node, "error": None}

    def write_index(entries, outdir):
        module.calls.append(("index", entries, outdir))
        path = Path(outdir) / "indice.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("| fase | archivo | nodo | OCR |\n", encoding="utf-8")
        return str(path)

    module.phases_from_spec = phases_from_spec
    module.capture_phase = capture_phase
    module.write_index = write_index
    module.phases = phases
    monkeypatch.setitem(sys.modules, "captures", module)
    monkeypatch.delitem(sys.modules, "webui_capture", raising=False)
    return module


@pytest.fixture
def webui_module(monkeypatch):
    module = ModuleType("webui_capture")
    module.calls = []
    monkeypatch.setenv("PFSENSE_PASSWORD", "clave-falsa-capmcp")
    module.available_result = (True, "")
    module.capture_result = {"ok": True, "captures": [{"page": "interfaces"}]}

    class WebUICapture:
        @classmethod
        def from_env(cls, outdir, host=None):
            module.calls.append(("from_env", outdir, host))
            return cls()

        def available(self):
            module.calls.append(("available",))
            return module.available_result

        def capture(self):
            module.calls.append(("capture",))
            return module.capture_result

    module.WebUICapture = WebUICapture
    monkeypatch.setitem(sys.modules, "webui_capture", module)
    return module


def _sin_modulos(monkeypatch, tmp_path):
    monkeypatch.delitem(sys.modules, "captures", raising=False)
    monkeypatch.delitem(sys.modules, "webui_capture", raising=False)
    monkeypatch.setattr(server, "__file__", str(tmp_path / "gns3_mcp_server.py"))


def _console_double(monkeypatch):
    proyecto = {"project_id": "p1", "name": "lab"}
    nodo = {"node_id": "n1", "name": "PF1", "node_type": "qemu", "status": "started",
            "properties": {"hda_disk_image": "pf.qcow2"}}
    cliente = SimpleNamespace(
        resolve_project=lambda _project: proyecto,
        find_node=lambda _pid, _node: nodo,
    )
    monitor = SimpleNamespace(closed=False)
    monitor.close = lambda: setattr(monitor, "closed", True)
    monkeypatch.setattr(server, "_client", lambda: cliente)
    monkeypatch.setattr(server.core.QemuMonitor, "for_node", lambda **_kwargs: monitor)
    return monitor


def test_firma_publica_y_registro():
    assert list(inspect.signature(server.gns3_capturas).parameters) == [
        "action", "project", "spec", "node", "outdir", "phase",
    ]
    assert "gns3_capturas" in server._registered_tool_functions()


def test_carga_dinamica_se_cachea(tmp_path, monkeypatch):
    (tmp_path / "captures.py").write_text("VALOR = 42\n", encoding="utf-8")
    monkeypatch.setattr(server, "__file__", str(tmp_path / "gns3_mcp_server.py"))
    monkeypatch.delitem(sys.modules, "captures", raising=False)

    primero = server._capture_module("captures.py")
    segundo = server._capture_module("captures.py")

    assert primero is segundo
    assert primero.VALOR == 42
    assert sys.modules["captures"] is primero


def test_phases_delega_en_la_spec_sin_escribir(captures_module, tmp_path):
    spec = {"captures": [{"phase": "topologia", "after": "apply"}]}

    result = server.gns3_capturas(action="phases", spec=spec, outdir=str(tmp_path))

    assert result == {"ok": True, "action": "phases", "phases": captures_module.phases}
    assert captures_module.calls == [("phases", spec)]
    assert list(tmp_path.iterdir()) == []


def test_phases_lee_gns3_lab_spec(captures_module, tmp_path, monkeypatch):
    ruta = tmp_path / "lab.yaml"
    ruta.write_text("captures:\n  - phase: topologia\n    after: apply\n", encoding="utf-8")
    monkeypatch.setenv("GNS3_LAB_SPEC", str(ruta))

    result = server.gns3_capturas(action="phases")

    assert result["ok"] is True
    assert captures_module.calls[0][1]["captures"][0]["phase"] == "topologia"


def test_console_conecta_hmp_delega_y_cierra(captures_module, tmp_path, monkeypatch):
    proyecto = {"project_id": "p1", "name": "lab"}
    nodo = {"node_id": "n1", "name": "PF1", "node_type": "qemu", "status": "started",
            "properties": {"hda_disk_image": "pf.qcow2"}}
    cliente = SimpleNamespace(
        resolve_project=lambda _project: proyecto,
        find_node=lambda _pid, _node: nodo,
    )
    monitor = SimpleNamespace(closed=False)
    monitor.close = lambda: setattr(monitor, "closed", True)
    monitor_calls = []

    def for_node(**kwargs):
        monitor_calls.append(kwargs)
        return monitor

    monkeypatch.setattr(server, "_client", lambda: cliente)
    monkeypatch.setattr(server.core.QemuMonitor, "for_node", for_node)

    result = server.gns3_capturas(
        action="console", project="lab", node="PF1", phase="topologia", outdir=str(tmp_path))

    assert result["ok"] is True
    assert result["action"] == "console"
    assert monitor_calls == [{"node_id": "n1", "disk": "pf.qcow2"}]
    assert captures_module.calls == [("console", monitor, "topologia", str(tmp_path), "PF1")]
    assert monitor.closed is True


def test_console_preserva_la_ruta_bajo_home_admin(captures_module, tmp_path, monkeypatch):
    monkeypatch.setenv("PFSENSE_USER", "admin")
    ruta = "/home/admin/capturas/01-topologia.png"
    monkeypatch.setattr(
        captures_module, "capture_phase",
        lambda _monitor, _phase, _outdir, node=None: {"ok": True, "path": ruta, "node": node})
    monitor = _console_double(monkeypatch)

    result = server.gns3_capturas(
        action="console", project="lab", node="PF1", phase="topologia", outdir=str(tmp_path))

    assert result["path"] == ruta
    assert result["node"] == "PF1"
    assert monitor.closed is True


def test_console_exige_nodo_fase_y_outdir(captures_module, tmp_path):
    result = server.gns3_capturas(action="console", project="lab", outdir=str(tmp_path))

    assert result["ok"] is False
    assert "node" in result["error"]
    assert captures_module.calls == []


def test_webui_delega_y_devuelve_su_resultado(captures_module, webui_module, tmp_path):
    result = server.gns3_capturas(action="webui", outdir=str(tmp_path))

    assert result["ok"] is True
    assert result["action"] == "webui"
    assert result["captures"] == [{"page": "interfaces"}]
    assert webui_module.calls == [("from_env", str(tmp_path), None), ("available",), ("capture",)]


def test_webui_preserva_las_rutas_bajo_home_admin(webui_module, tmp_path, monkeypatch):
    monkeypatch.setenv("PFSENSE_USER", "admin")
    rutas = [
        "/home/admin/capturas/01-interfaces.png",
        "/home/admin/capturas/02-rules.png",
    ]
    webui_module.capture_result = {
        "ok": True,
        "captures": [{"page": "interfaces", "path": rutas[0]},
                     {"page": "rules", "path": rutas[1]}],
    }

    result = server.gns3_capturas(action="webui", outdir=str(tmp_path))

    assert [capture["path"] for capture in result["captures"]] == rutas


def test_webui_preserva_ruta_y_redacta_solo_el_error(webui_module, tmp_path, monkeypatch):
    secreto = "clave-falsa-capmcp-ruta-77b2"
    monkeypatch.setenv("PFSENSE_USER", "admin")
    monkeypatch.setenv("PFSENSE_PASSWORD", secreto)
    ruta = "/home/admin/capturas/01-interfaces.png"
    webui_module.capture_result = {
        "ok": False,
        "captures": [{"page": "interfaces", "path": ruta}],
        "reason": f"captura fallida con {secreto}",
    }

    result = server.gns3_capturas(action="webui", outdir=str(tmp_path))
    texto = json.dumps(result, ensure_ascii=False)

    assert result["captures"][0]["path"] == ruta
    assert result["fallback"] == "consola"
    assert secreto not in texto
    assert "[redactado]" in result["reason"]


def test_webui_no_disponible_degrada_a_consola(webui_module, tmp_path):
    webui_module.available_result = (False, "Playwright no está instalado")

    result = server.gns3_capturas(action="webui", outdir=str(tmp_path))

    assert result == {"ok": False, "action": "webui", "error": "Playwright no está instalado",
                      "reason": "Playwright no está instalado", "fallback": "consola"}
    assert ("capture",) not in webui_module.calls


def test_webui_sin_credenciales_no_llama_from_env(webui_module, tmp_path, monkeypatch):
    monkeypatch.delenv("PFSENSE_PASSWORD", raising=False)

    result = server.gns3_capturas(action="webui", outdir=str(tmp_path))

    assert result["ok"] is False
    assert result["fallback"] == "consola"
    assert "PFSENSE_PASSWORD" in result["reason"]
    assert webui_module.calls == []


def test_webui_redacta_credenciales_en_errores(webui_module, tmp_path, monkeypatch):
    secreto = "clave-falsa-capmcp-913b"
    monkeypatch.setenv("PFSENSE_PASSWORD", secreto)
    webui_module.capture_result = None

    class Rota:
        @classmethod
        def from_env(cls, outdir, host=None):
            return cls()

        def available(self):
            return True, ""

        def capture(self):
            raise RuntimeError(f"login fallido con {secreto}")

    webui_module.WebUICapture = Rota

    result = server.gns3_capturas(action="webui", outdir=str(tmp_path))
    texto = json.dumps(result, ensure_ascii=False)

    assert result["ok"] is False
    assert result["fallback"] == "consola"
    assert secreto not in texto
    assert "[redactado]" in texto


def test_index_escribe_las_entradas_pasadas(captures_module, tmp_path):
    entries = [{"phase": "topologia", "path": "01-topologia.png", "node": "PF1", "ocr": "ok"}]

    result = server.gns3_capturas(action="index", spec=entries, outdir=str(tmp_path))

    assert result["ok"] is True
    assert result["action"] == "index"
    assert result["path"] == str(tmp_path / "indice.md")
    assert captures_module.calls == [("index", entries, str(tmp_path))]
    assert (tmp_path / "indice.md").is_file()


def test_index_devuelve_la_ruta_real_sin_redactar_el_usuario(captures_module, tmp_path, monkeypatch):
    monkeypatch.setenv("GNS3_USER", "admin")
    ruta = "/home/admin/capturas/indice.md"
    monkeypatch.setattr(captures_module, "write_index", lambda _entries, _outdir: ruta)

    result = server.gns3_capturas(
        action="index", spec=[{"phase": "topologia"}], outdir=str(tmp_path))

    assert result == {"ok": True, "action": "index", "path": ruta}


def test_index_sin_entradas_devuelve_el_indice_existente(captures_module, tmp_path):
    indice = tmp_path / "indice.md"
    indice.write_text("índice existente\n", encoding="utf-8")

    result = server.gns3_capturas(action="index", outdir=str(tmp_path))

    assert result == {"ok": True, "action": "index", "path": str(indice), "existing": True}
    assert captures_module.calls == []
    assert indice.read_text(encoding="utf-8") == "índice existente\n"


@pytest.mark.parametrize("action", ["phases", "console", "index", "webui"])
def test_modulo_ausente_devuelve_error_con_su_nombre(action, tmp_path, monkeypatch):
    _sin_modulos(monkeypatch, tmp_path)
    monkeypatch.setenv("PFSENSE_PASSWORD", "clave-falsa")

    result = server.gns3_capturas(
        action=action, project="lab", node="PF1", phase="topologia", outdir=str(tmp_path))

    assert result["ok"] is False
    esperado = "webui_capture.py" if action == "webui" else "captures.py"
    assert esperado in result["error"]


def test_accion_desconocida_lista_las_cuatro_validas():
    result = server.gns3_capturas(action="nope")

    assert result["valid"] == ["phases", "console", "webui", "index"]
    assert "gns3_capturas" in result["hint"]
