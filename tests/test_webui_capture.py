"""Contrato de capturas WebUI y `gns3lab examen capturas` sin red real."""
from __future__ import annotations

import builtins
import importlib.util
import json
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

import pytest

import webui_capture as webui


CLI_PATH = Path(__file__).resolve().parents[1] / "cli" / "gns3lab"
LOADER = SourceFileLoader("gns3lab_webtests", str(CLI_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
cli = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cli
LOADER.exec_module(cli)


class FakePage:
    def __init__(self, screenshot_error: str | None = None):
        self.calls: list[tuple] = []
        self.screenshot_error = screenshot_error

    def goto(self, url, **kwargs):
        self.calls.append(("goto", url, kwargs))

    def fill(self, selector, value):
        self.calls.append(("fill", selector, value))

    def click(self, selector):
        self.calls.append(("click", selector))

    def wait_for_load_state(self, state):
        self.calls.append(("wait", state))

    def screenshot(self, path, **kwargs):
        self.calls.append(("screenshot", path, kwargs))
        if self.screenshot_error:
            raise RuntimeError(self.screenshot_error)
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n")


class FakeContext:
    def __init__(self, page):
        self.pages = [page]
        self.closed = False

    def new_page(self):
        return self.pages[0]

    def set_default_timeout(self, timeout):
        self.timeout = timeout

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, context):
        self.context = context
        self.kwargs = None

    def launch_persistent_context(self, **kwargs):
        self.kwargs = kwargs
        return self.context


class FakePlaywright:
    def __init__(self, page):
        self.chromium = FakeChromium(FakeContext(page))
        self.stopped = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stopped = True


@pytest.fixture
def fake_playwright(monkeypatch):
    def install(page=None):
        page = page or FakePage()
        playwright = FakePlaywright(page)
        monkeypatch.setattr(webui, "_sync_playwright", lambda: playwright)
        monkeypatch.setattr(webui.WebUICapture, "available", lambda self: (True, ""))
        return playwright, page

    return install


def test_import_playwright_es_perezoso_y_explica_como_instalarlo(monkeypatch):
    real_import = builtins.__import__

    def sin_playwright(name, *args, **kwargs):
        if name == "playwright.sync_api":
            raise ModuleNotFoundError("No module named 'playwright'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", sin_playwright)

    with pytest.raises(webui.WebUIUnavailable) as excinfo:
        webui._sync_playwright()

    assert "Playwright" in str(excinfo.value)
    assert "playwright install chromium" in str(excinfo.value)


def test_from_env_usa_host_override_y_nunca_imprime_la_password(monkeypatch, tmp_path):
    monkeypatch.setenv("PFSENSE_HOST", "192.0.2.10")
    monkeypatch.setenv("PFSENSE_USER", "admin")
    monkeypatch.setenv("PFSENSE_PASSWORD", "clave-ficticia")

    capture = webui.WebUICapture.from_env(str(tmp_path), host="192.0.2.20")

    assert capture.host == "192.0.2.20"
    assert capture.user == "admin"
    assert capture.password == "clave-ficticia"
    assert capture.port == 443
    assert capture.outdir == str(tmp_path)

    monkeypatch.delenv("PFSENSE_PASSWORD")
    with pytest.raises(webui.WebUIUnavailable) as excinfo:
        webui.WebUICapture.from_env(str(tmp_path))
    assert "PFSENSE_PASSWORD" in str(excinfo.value)
    assert "clave-ficticia" not in str(excinfo.value)


def test_available_sin_playwright_no_intenta_red(monkeypatch, tmp_path):
    def sin_red(*args, **kwargs):
        raise AssertionError("sin Playwright no debe probar HTTPS")

    monkeypatch.setattr(
        webui, "_sync_playwright",
        lambda: (_ for _ in ()).throw(webui.WebUIUnavailable("Playwright no instalado")),
    )
    monkeypatch.setattr(webui, "_probe_https", sin_red)

    ok, reason = webui.WebUICapture("192.0.2.1", "admin", "ficticia", str(tmp_path)).available()

    assert ok is False
    assert reason == "Playwright no instalado"


def test_available_comprueba_tcp_y_https(monkeypatch, tmp_path):
    llamadas = []
    monkeypatch.setattr(webui, "_sync_playwright", lambda: object())
    monkeypatch.setattr(
        webui, "_probe_https",
        lambda host, port, timeout: llamadas.append((host, port, timeout)),
    )
    capture = webui.WebUICapture("192.0.2.1", "admin", "ficticia", str(tmp_path), port=8443,
                                 timeout=1.5)

    assert capture.available() == (True, "")
    assert llamadas == [("192.0.2.1", 8443, 1.5)]

    monkeypatch.setattr(
        webui, "_probe_https",
        lambda *args: (_ for _ in ()).throw(
            webui.WebUIUnavailable("HTTPS no responde en 192.0.2.1:8443")
        ),
    )
    assert capture.available() == (False, "HTTPS no responde en 192.0.2.1:8443")


def test_capture_por_defecto_hace_login_una_vez_y_cierra_perfil(
    fake_playwright, tmp_path,
):
    playwright, page = fake_playwright()
    capture = webui.WebUICapture("192.0.2.1", "admin", "clave-ficticia", str(tmp_path))

    result = capture.capture()

    assert result["ok"] is True
    assert result["reason"] is None
    assert result["fallback"] is None
    assert [Path(item["path"]).name for item in result["captures"]] == [
        "01-interfaces.png", "02-rules.png", "03-dhcp.png",
    ]
    assert all(Path(item["path"]).is_file() for item in result["captures"])

    fills = [call for call in page.calls if call[0] == "fill"]
    assert fills == [
        ("fill", 'input[name="username"]', "admin"),
        ("fill", 'input[name="password"]', "clave-ficticia"),
    ]
    clicks = [call[1] for call in page.calls if call[0] == "click"]
    assert len(clicks) == 1
    assert "password" in clicks[0]
    assert "save" not in clicks[0].lower()
    assert "apply" not in clicks[0].lower()
    assert [call[1] for call in page.calls if call[0] == "goto"] == [
        "https://192.0.2.1:443/",
        "https://192.0.2.1:443/interfaces.php",
        "https://192.0.2.1:443/firewall_rules.php",
        "https://192.0.2.1:443/services_dhcp.php",
    ]
    assert playwright.chromium.kwargs["headless"] is True
    assert playwright.chromium.kwargs["ignore_https_errors"] is True
    perfil = Path(playwright.chromium.kwargs["user_data_dir"])
    assert perfil.parent == Path("/tmp")
    assert not perfil.exists()
    assert playwright.chromium.context.closed is True
    assert playwright.stopped is True


def test_capture_acepta_paginas_y_sanitiza_el_nombre(fake_playwright, tmp_path):
    _, page = fake_playwright()
    capture = webui.WebUICapture("192.0.2.1", "admin", "ficticia", str(tmp_path))

    result = capture.capture([("reglas LAN", "/firewall_rules.php?view=lan")])

    assert result["ok"] is True
    assert Path(result["captures"][0]["path"]).name == "01-reglas-LAN.png"
    assert page.calls[-2][1] == "https://192.0.2.1:443/firewall_rules.php?view=lan"


def test_capture_no_disponible_devuelve_fallback_sin_lanzar_navegador(
    monkeypatch, tmp_path,
):
    def no_navegador():
        raise AssertionError("no debe lanzar navegador")

    monkeypatch.setattr(webui, "_sync_playwright", no_navegador)
    monkeypatch.setattr(
        webui.WebUICapture, "available",
        lambda self: (False, "Playwright no está instalado"),
    )
    capture = webui.WebUICapture("192.0.2.1", "admin", "ficticia", str(tmp_path))

    result = capture.capture()

    assert result["ok"] is False
    assert result["captures"] == []
    assert "Playwright" in result["reason"]
    assert result["fallback"] == "consola"


def test_capture_cierra_recursos_y_oculta_password_si_screenshot_falla(
    fake_playwright, tmp_path,
):
    page = FakePage(screenshot_error="fallo con clave-ficticia")
    playwright, _ = fake_playwright(page)
    capture = webui.WebUICapture("192.0.2.1", "admin", "clave-ficticia", str(tmp_path))

    result = capture.capture()

    assert result["ok"] is False
    assert result["fallback"] == "consola"
    assert "clave-ficticia" not in result["reason"]
    assert "***" in result["reason"]
    assert playwright.chromium.context.closed is True
    assert playwright.stopped is True


def _run_cli(monkeypatch, argv, tmp_path):
    conf = {"servers": {}, "default_server": "local"}
    conf_path = tmp_path / "gns3lab.json"
    conf_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cli, "CONF", conf_path)
    monkeypatch.setattr(cli, "load_conf", lambda: conf)
    monkeypatch.setattr(sys, "argv", ["gns3lab", *argv])
    try:
        return cli.main()
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1


def test_cli_capturas_webui_json_no_consulta_servidor(monkeypatch, tmp_path, capsys):
    visto = {}
    esperado = {
        "ok": True,
        "captures": [{"page": "interfaces", "path": str(tmp_path / "01-interfaces.png")}],
        "reason": None,
        "fallback": None,
    }

    def fake_from_env(cls, outdir, host=None):
        visto.update(outdir=outdir, host=host)
        return SimpleNamespace(available=lambda: (True, ""), capture=lambda: esperado)

    def no_servidor(*args, **kwargs):
        raise AssertionError("la captura WebUI no debe consultar GNS3")

    monkeypatch.setattr(webui.WebUICapture, "from_env", classmethod(fake_from_env))
    monkeypatch.setattr(cli, "Server", no_servidor)

    rc = _run_cli(monkeypatch, [
        "examen", "capturas", "--webui", "--host", "192.0.2.30",
        "--out", str(tmp_path), "--phase", "reglas", "--json",
    ], tmp_path)

    captured = capsys.readouterr()
    assert rc == 0
    assert json.loads(captured.out) == esperado
    assert captured.err == ""
    assert visto == {"outdir": str(tmp_path), "host": "192.0.2.30"}


def test_cli_capturas_sin_webui_avisa_que_capcore_esta_pendiente(
    monkeypatch, tmp_path, capsys,
):
    monkeypatch.setitem(sys.modules, "captures", None)

    rc = _run_cli(monkeypatch, ["examen", "capturas", "--out", str(tmp_path), "--json"], tmp_path)

    captured = capsys.readouterr()
    assert rc == 1
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert "previsto en capcore" in payload["reason"]


def test_cli_webui_no_disponible_delega_fallback_en_consola(
    monkeypatch, tmp_path, capsys,
):
    fake_capture = SimpleNamespace(available=lambda: (False, "HTTPS no responde"))
    monkeypatch.setattr(
        webui.WebUICapture, "from_env",
        classmethod(lambda cls, outdir, host=None: fake_capture),
    )
    monitor = SimpleNamespace(closed=False)
    monitor.close = lambda: setattr(monitor, "closed", True)
    llamadas = []

    def capture_phase(mon, phase, outdir, node=None):
        llamadas.append((mon, phase, outdir, node))
        return {"ok": True, "phase": phase, "path": str(Path(outdir) / "01-reglas.png"),
                "ocr": "pfSense", "node": node, "error": None}

    monkeypatch.setitem(sys.modules, "captures", SimpleNamespace(capture_phase=capture_phase))
    monkeypatch.setattr(cli, "Server", lambda *args: SimpleNamespace(name="falso"))
    monkeypatch.setattr(cli, "_monitor", lambda *args: monitor)

    rc = _run_cli(monkeypatch, [
        "examen", "capturas", "--webui", "--out", str(tmp_path),
        "--phase", "reglas", "--name", "Kit de examen", "--json",
    ], tmp_path)

    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["fallback"] == "consola"
    assert payload["reason"] == "HTTPS no responde"
    assert "HTTPS no responde" in captured.err
    assert llamadas == [(monitor, "reglas", str(tmp_path), "PF1")]
    assert monitor.closed is True
