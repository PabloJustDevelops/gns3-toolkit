"""Capturas de solo lectura de la WebUI de pfSense con Playwright opcional.

El módulo se importa sin Playwright. Si se quiere usar el navegador, instálalo
en el entorno del usuario (no se instala nada desde esta herramienta)::

    python -m pip install playwright
    playwright install chromium

La WebUI es solo evidencia visual: el único formulario que se envía es el de
login. Nunca se pulsa Save/Apply ni se envía un formulario de configuración.
"""
from __future__ import annotations

import os
import re
import socket
import ssl
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


DEFAULT_PAGES = (
    ("interfaces", "/interfaces.php"),
    ("rules", "/firewall_rules.php"),
    ("dhcp", "/services_dhcp.php"),
)


class WebUIUnavailable(RuntimeError):
    """La WebUI no puede usarse; la llamada debe degradar a consola."""


def _sync_playwright():
    """Importa Playwright solo cuando hace falta, con un error accionable."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise WebUIUnavailable(
            "Playwright no está instalado; instálalo con `python -m pip install "
            "playwright` y ejecuta `playwright install chromium`"
        ) from exc
    return sync_playwright


def _probe_https(host: str, port: int, timeout: float) -> None:
    """Comprueba TCP y el handshake TLS sin validar el certificado autofirmado."""
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=host):
                pass
    except OSError as exc:
        raise WebUIUnavailable(f"HTTPS no responde en {host}:{port}: {exc}") from exc


def _safe_reason(exc: BaseException, password: str) -> str:
    """Evita que una excepción del navegador filtre la contraseña."""
    return str(exc).replace(password, "***") if password else str(exc)


def _result(ok: bool, captures: list[dict], reason: str | None = None) -> dict:
    return {
        "ok": bool(ok),
        "captures": captures,
        "reason": reason,
        "fallback": None if ok else "consola",
    }


class WebUICapture:
    """Login único y capturas PNG de páginas de solo lectura de pfSense."""

    def __init__(self, host: str, user: str, password: str, outdir: str,
                 port: int = 443, timeout: float = 8.0):
        self.host = str(host)
        self.user = str(user)
        self.password = str(password)
        self.outdir = str(outdir)
        self.port = int(port)
        self.timeout = float(timeout)
        if not self.host:
            raise WebUIUnavailable("falta el host de la WebUI")
        if self.port <= 0:
            raise WebUIUnavailable("el puerto de la WebUI debe ser mayor que cero")
        if self.timeout <= 0:
            raise WebUIUnavailable("el timeout de la WebUI debe ser mayor que cero")

    @classmethod
    def from_env(cls, outdir: str, host: str | None = None) -> "WebUICapture":
        """Carga PFSENSE_HOST/USER/PASSWORD; el puerto WebUI es 443 por defecto."""
        password = os.environ.get("PFSENSE_PASSWORD")
        if not password:
            raise WebUIUnavailable("falta la variable de entorno PFSENSE_PASSWORD")
        return cls(
            host=host or os.environ.get("PFSENSE_HOST") or "192.168.1.1",
            user=os.environ.get("PFSENSE_USER") or "admin",
            password=password,
            outdir=outdir,
        )

    def available(self) -> tuple[bool, str]:
        """Devuelve si Playwright es importable y TCP/HTTPS responde."""
        try:
            _sync_playwright()
        except WebUIUnavailable as exc:
            return False, str(exc)
        try:
            _probe_https(self.host, self.port, self.timeout)
        except WebUIUnavailable as exc:
            return False, str(exc)
        return True, ""

    def _base_url(self) -> str:
        host = f"[{self.host}]" if ":" in self.host and not self.host.startswith("[") else self.host
        return f"https://{host}:{self.port}"

    def _page_url(self, path: str) -> str:
        parsed = urlsplit(path)
        if parsed.scheme or parsed.netloc or not path.startswith("/") or path.startswith("//"):
            raise WebUIUnavailable("la página WebUI debe ser una ruta relativa a pfSense")
        return self._base_url() + path

    @staticmethod
    def _filename(index: int, page: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9_-]+", "-", page).strip("-_") or "pagina"
        return f"{index:02d}-{slug}.png"

    @staticmethod
    def _login_failure(page) -> str | None:
        """Detecta el formulario de acceso o el error que publica pfSense 2.7.2."""
        parsed = urlsplit(str(getattr(page, "url", "")))
        if parsed.path.lower().rstrip("/").rsplit("/", 1)[-1] in {"login", "login.php"}:
            return "login rechazado por pfSense: la URL sigue en el formulario de acceso"

        error = page.locator("body#login .msgbox.text-danger h4")
        if error.count():
            detail = error.first.inner_text().strip()
            suffix = f": {detail}" if detail else ""
            return f"login rechazado por pfSense{suffix}"

        if page.locator("#passwordfld").count():
            return "login rechazado por pfSense: sigue visible el formulario de acceso"
        return None

    @staticmethod
    def _comprobar_respuesta(response, url: str) -> None:
        """Playwright devuelve la respuesta final; ``None`` no permite validarla."""
        if response is None:
            raise WebUIUnavailable(f"sin respuesta al abrir {url}")
        estado = getattr(response, "status", None)
        if estado is not None and int(estado) >= 400:
            raise WebUIUnavailable(f"HTTP {estado} al abrir {url}")

    @classmethod
    def _validar_navegacion(cls, page, response, url: str) -> None:
        """Descarta error HTTP, redirect al login y páginas distintas de la pedida."""
        cls._comprobar_respuesta(response, url)
        final = urlsplit(str(getattr(page, "url", "")))
        if final.path.lower().rstrip("/").rsplit("/", 1)[-1] in {"login", "login.php"}:
            raise WebUIUnavailable(f"navegación a {url} redirigida al login de pfSense")
        esperado = urlsplit(url)
        if final.path != esperado.path or (final.netloc and final.netloc != esperado.netloc):
            raise WebUIUnavailable(
                f"navegación inesperada al abrir {url}: {final.geturl() or 'sin URL'}")

    def capture(self, pages: list[tuple[str, str]] | None = None) -> dict:
        """Hace login una vez y captura las páginas; cualquier fallo cae a consola."""
        available, reason = self.available()
        if not available:
            return _result(False, [], reason)

        selected = DEFAULT_PAGES if pages is None else pages
        outdir = Path(self.outdir).expanduser()
        captures: list[dict] = []
        timeout_ms = max(1, int(self.timeout * 1000))
        try:
            outdir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="gns3-webui-", dir="/tmp") as profile:
                sync_playwright = _sync_playwright()
                with sync_playwright() as playwright:
                    context = None
                    try:
                        context = playwright.chromium.launch_persistent_context(
                            user_data_dir=profile,
                            headless=True,
                            ignore_https_errors=True,
                        )
                        context.set_default_timeout(timeout_ms)
                        page = context.pages[0] if context.pages else context.new_page()
                        inicio = self._base_url() + "/"
                        respuesta = page.goto(inicio, wait_until="domcontentloaded",
                                              timeout=timeout_ms)
                        self._comprobar_respuesta(respuesta, inicio)
                        page.fill("#usernamefld", self.user)
                        page.fill("#passwordfld", self.password)
                        page.click(
                            'form:has(#passwordfld) input[type="submit"], '
                            'form:has(#passwordfld) button[type="submit"]'
                        )
                        page.wait_for_load_state("domcontentloaded")
                        login_failure = self._login_failure(page)
                        if login_failure:
                            raise WebUIUnavailable(login_failure)

                        for index, (name, path) in enumerate(selected, 1):
                            url = self._page_url(path)
                            respuesta = page.goto(url, wait_until="domcontentloaded",
                                                  timeout=timeout_ms)
                            self._validar_navegacion(page, respuesta, url)
                            destination = outdir / self._filename(index, name)
                            page.screenshot(path=str(destination), full_page=True)
                            captures.append({"page": name, "path": str(destination)})
                    finally:
                        if context is not None:
                            context.close()
        except Exception as exc:
            return _result(False, captures, _safe_reason(exc, self.password))
        return _result(True, captures)
