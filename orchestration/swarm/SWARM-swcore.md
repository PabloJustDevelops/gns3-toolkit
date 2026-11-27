# SWARM-swcore — informe de hallazgos

- Fecha: 2026-11-27
- Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-swcore`
- Rama: `opencode/swcore` @ `ce2b20eda644acc6e19030f5f62c92d9be6e2d92`
- Base: `master` @ mismo commit; `git rev-list --count master..HEAD` → `0`; `git status --porcelain` → vacío
- Entorno: Python 3.12.14 (venv `.venv/`), pytest 9.2.0

## Honestidad sobre el origen del informe

No había informe previo en `orchestration/SWARM-swcore.md` (no existía el fichero; `orchestration/`
sólo contiene `BRIEF-*.md`, `SWARM-*` no aparece). En esta sesión no se revisó ningún diff externo:
la rama no tiene commits propios ni cambios sin commit, así que no hay nada nuevo que auditar.
Los hallazgos de abajo provienen de **ejecutar los gates reales del repo en esta sesión** y capturar
la salida literal. No se ha modificado código ni tests; sólo se crea este fichero.

## Gates ejecutados (comando → exit code → salida relevante)

1. `source .venv/bin/activate && python -m pytest -q` → **exit 1** →
   `3 failed, 928 passed in 302.80s (0:05:02)`
   (suite sin servidor GNS3; `tests/test_mcp_smoke.py` ignorado por `tests/conftest.py`).
   Fallos, todos en `tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense`:
   - `[None-telnet]`
   - `[vnc-vnc]`
   - `[spice-spice]`
2. `.venv/bin/python -m pytest "tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense" -q`
   → **exit 1** → `3 failed in 1.23s`, mismo `AttributeError`.
3. `.venv/bin/python -m py_compile gns3core.py gns3_mcp_server.py cli/gns3lab` → **exit 0**.
4. `source .venv/bin/activate && pytest -q` (script de consola, la forma documentada en `AGENTS.md`)
   → **exit 2** → `5 errors in ~1.2s`, `Interrupted: 5 errors during collection`, **0 tests ejecutados**.
5. `.venv/bin/pytest -q` → mismo resultado que (4).

## Hallazgos (fichero:línea + reproducibilidad)

### H1 — `_examen_disk` exige `json_list_or_die` y el doble de test `ClienteExamenFalso` no la tiene

- **Dónde:**
  - `cli/gns3lab:3463` `def _examen_disk(c, preferred=None, en_uso=None)`;
    `cli/gns3lab:3470` `imagenes = c.json_list_or_die("/v2/computes/local/qemu/images", "imágenes QEMU")`.
  - Llamador: `cli/gns3lab:3519` `_examen_setup(...)`; `cli/gns3lab:3546`
    `disco, disponibles = _examen_disk(c, preferido, ocupados)`.
  - El método existe en producción: `gns3core.py:208`
    `def json_list_or_die(self, path, what, **kw) -> list` (`RuntimeError` si `st != 200` o no es lista).
    El `Client` real lo cumple; `_templates_or_die` (`cli/gns3lab:1001`) incluso degrada con
    `hasattr(c, "json_or_die")`, pero `_examen_disk` no.
  - El doble: `tests/test_pf_console.py:241` `class ClienteExamenFalso` — define `get`, `req`,
    `ensure_open`, `drawing_create`, `project_file_write`, `nodes_action`, `nodes`, `post`, `put`,
    `qemu_binaries`, `projects`, **no** `json_list_or_die`; su `get`
    (`tests/test_pf_console.py:250-265`) sólo sirve `/v2/templates` y `/nodes/...`, y devuelve
    `404, {"message": ...}` (`tests/test_pf_console.py:265`) para `/v2/computes/local/qemu/images`;
    ofrece un `qemu_images()` (`tests/test_pf_console.py:267`) que ningún código de producción llama.
- **Test que falla:** `tests/test_pf_console.py:318-329`
  `@pytest.mark.parametrize(("console_type","esperado"), [(None,"telnet"),("vnc","vnc"),("spice","spice")])`
  (`tests/test_pf_console.py:318`); def en `tests/test_pf_console.py:319`;
  llamada `rc = cli._examen_setup(args, {}, cliente, "Kit de examen")` en `tests/test_pf_console.py:325`.
- **Error literal:**
  `E   AttributeError: 'ClienteExamenFalso' object has no attribute 'json_list_or_die'`
  en `cli/gns3lab:3470`, alcanzado desde `tests/test_pf_console.py:325`, vía `cli/gns3lab:3546`.
- **Diagnóstico:** no es un bug de producción. `cli/gns3lab:3470` es código real contra `gns3core.Client`,
  que sí tiene `json_list_or_die` (`gns3core.py:208`). Es el doble de test quien está desactualizado
  para el camino `_examen_setup` → `_examen_disk` (no implementa `json_list_or_die`, no sirve
  `/v2/computes/local/qemu/images` como lista 200, y conserva `qemu_images()` heredado).
  Las tres parametrizaciones fallan antes de cualquier `assert`; el `console_type` pedido
  (`telnet` por defecto en `cli/gns3lab:3520`, validado `cli/gns3lab:3521-3522`) no llega a comprobarse.
- **Reproducibilidad (sin servidor GNS3):**
  ```bash
  cd /home/pablorg/Proyectos/gns3-toolkit-wt-swcore
  source .venv/bin/activate
  python -m pytest tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense -q
  ```
  → `3 failed in 1.23s`, `AttributeError: 'ClienteExamenFalso' object has no attribute 'json_list_or_die'`.
- **Corrección sugerida (no aplicada):** completar `ClienteExamenFalso` (`tests/test_pf_console.py:241`)
  con `json_list_or_die(path, what, **kw)`, sirviendo `200, [{"filename": "pfSense.qcow2"}]` para
  `/v2/computes/local/qemu/images`. Opcionalmente endurecer `_examen_disk` (`cli/gns3lab:3470`) con el
  mismo patrón `hasattr(c, ...)` que `_templates_or_die` (`cli/gns3lab:1003`), pero eso cambiaría
  semántica real (hoy un listado que falla mata el comando, ver `gns3core.py:209-213`); la mínima es
  arreglar el doble.

### H2 — `pytest -q` (script de consola) no arranca en este worktree: `No module named 'gns3core'` / `gns3_mcp_server`

- **Dónde:**
  - `pytest.ini:1-2` → sólo `testpaths = tests`; sin `pythonpath = .`.
  - `requirements.txt` → `fastmcp, httpx, pillow, pyyaml, pytest, pytest-cov`; el propio repo no se
    instala como paquete. `scripts/install.sh` hace `uv pip install -r requirements.txt`
    (`scripts/install.sh:16`) y sólo inserta `sys.path.insert(0, ".")` ad hoc en su check MCP
    (`scripts/install.sh:30`).
  - Con pytest 9.2.0, el script de consola no añade el `rootdir` a `sys.path`; pytest sólo antepone
    el directorio de cada test (`tests/`, sin `__init__.py`) y `tests/conftest.py`.
  - `AGENTS.md` (sección «Cómo se ejecuta») documenta `source .venv/bin/activate` + `pytest -q`.
- **Error literal (x5, un módulo cada uno):**
  - `ERROR tests/test_api_candidates.py` → `E ModuleNotFoundError: No module named 'gns3_mcp_server'`
    (`tests/test_api_candidates.py:14` `import gns3_mcp_server as server`)
  - `ERROR tests/test_api_gaps.py` → `E ModuleNotFoundError: No module named 'gns3_mcp_server'`
    (`tests/test_api_gaps.py:12`)
  - `ERROR tests/test_api_map.py` → `E ModuleNotFoundError: No module named 'gns3core'`
    (`tests/test_api_map.py:2` `from gns3core import API_V2_MAP`)
  - `ERROR tests/test_batch.py` → `E ModuleNotFoundError: No module named 'gns3_mcp_server'`
    (`tests/test_batch.py:11`)
  - `ERROR tests/test_binary_download.py` → `E ModuleNotFoundError: No module named 'gns3_mcp_server'`
  - `!!!!!!!!!!!!!!!!!!! Interrupted: 5 errors during collection !!!!!!!!!!!!!!!!!! 5 errors in 1.50s`
- **Diagnóstico:** entorno/invocación, no código bajo test. `python -m pytest` añade el `cwd` a
  `sys.path` y funciona; `.venv/bin/python -c 'import gns3core'` desde la raíz funciona. Sin servidor
  GNS3 no cambia nada. En este worktree `pytest` no está en `PATH` fuera del venv.
- **Reproducibilidad:**
  ```bash
  cd /home/pablorg/Proyectos/gns3-toolkit-wt-swcore
  source .venv/bin/activate
  pytest -q                 # → 5 errores de colección, exit 2
  python -m pytest -q       # → la suite corre; exit 1 con los 3 fallos de H1
  ```
- **Corrección sugerida (no aplicada):** añadir `pythonpath = .` a `pytest.ini`, o documentar
  `python -m pytest -q` en `AGENTS.md`, o instalar el repo (`uv pip install -e .`).

## Sin otros hallazgos

- `py_compile` de los tres puntos de entrada: OK.
- Sin cambios en GNS3, sin comandos con efectos laterales (sólo lectura + este fichero).
- No hay hallazgos de seguridad, docs ni estilo verificados en esta sesión; no se afirma «sin hallazgos»
  más allá de lo ejecutado arriba. Todo lo no ejecutado queda como no verificado.
