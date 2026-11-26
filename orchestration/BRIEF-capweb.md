# BRIEF — carril `capweb` (capturas de la WebUI de pfSense con navegador headless)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-capweb` · rama `opencode/capweb`.

## Contexto

El profesor puede pedir capturas de la WebUI de pfSense. Lee `AGENTS.md`, `pfsense.py`
(`from_env`, credenciales solo de entorno), `cli/gns3lab` (`cmd_pf`, `cmd_examen`) y
`docs/PFSENSE-NATIVO.md`.

**La WebUI solo se usa para evidencia visual**: nunca se configura nada desde el navegador. No
VNC. Si el navegador o la IP no están disponibles, se degrada a captura de consola HMP sin
bloquear el examen.

## Contrato

Fichero nuevo `webui_capture.py`, import lazy de Playwright (el módulo debe importarse y
funcionar aunque Playwright no esté instalado):

```python
class WebUIUnavailable(RuntimeError): ...

class WebUICapture:
    def __init__(self, host: str, user: str, password: str, outdir: str,
                 port: int = 443, timeout: float = 8.0)
    @classmethod
    def from_env(cls, outdir: str, host: str | None = None)  # PFSENSE_HOST/USER/PASSWORD
    def available(self) -> tuple[bool, str]   # Playwright importable + TCP/HTTPS responde;
                                             # devuelve (False, razón literal) si no
    def capture(self, pages: list[tuple[str, str]] | None = None) -> dict
        # páginas por defecto: ("interfaces", "/interfaces.php"),
        # ("rules", "/firewall_rules.php"), ("dhcp", "/services_dhcp.php")
        # login_once, ignore_https_errors=True, perfil efímero bajo /tmp,
        # screenshot PNG por página con nombre NN-<pagina>.png, cerrar en finally.
        # NUNCA hacer clic en Save/Apply ni enviar formularios de configuración.
        # Devuelve {"ok", "captures": [...], "reason", "fallback": "consola"}.
```

En `cli/gns3lab`, añadir a `cmd_examen` la acción `capturas` con opciones `--webui`,
`--host`, `--out`, `--phase`, `--json`. Sin `--webui` delega en `captures.capture_phase` del
carril capcore (si no está aún, error claro «previsto en capcore»). Con `--webui` usa
`WebUICapture.from_env`; si `available()` es False, imprime la razón y captura por consola.

## Reglas

- Credenciales solo de entorno; nunca escribirlas en repo, logs ni nombres de fichero.
- No instalar Playwrightni Chromium en el sistema ni en el venv durante esta tarea: si faltan,
  el código degrada con razón explícita. Documenta en el docstring el comando que el usuario
  ejecutaría si quiere instalarlos (`playwright install chromium`).
- Tests con dobles de `sync_playwright` y `page.screenshot`: sin red, sin pfSense real,
  sin credenciales reales. Comprobar que no se llama a Save/Apply.

## Gates

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-capweb
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile webui_capture.py cli/gns3lab
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q tests/test_webui_capture.py
python3 scripts/verify.py
```

Commit en `opencode/capweb`; **no push a master**, no PR.
