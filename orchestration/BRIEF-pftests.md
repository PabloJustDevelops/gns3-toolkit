# BRIEF — carril `pftests` (tests de pfSense nativo y velocidad)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-pftests` · rama `opencode/pftests`.

## Contexto

Los carriles `pfcore`, `pfmcp` y `pfcli` añaden `pfsense.py`, la tool `gns3_pfsense` y los
comandos `gns3lab pf`, más la paralelización de `gns3_batch`. Hay que cubrirlos sin servidor
GNS3 ni host pfSense. Lee `AGENTS.md`, `PROJECT.md`, `tests/conftest.py` y los briefs
`BRIEF-pfcore.md`, `BRIEF-pfmcp.md`, `BRIEF-pfcli.md`.

## Objetivo

1. Mantener **100 % de cobertura de `gns3core.py`** (`--cov=gns3core --cov-fail-under=100`) y
   añadir cobertura de `pfsense.py` (`--cov=pfsense`) con objetivo ≥90 %.
2. `tests/test_pfsense.py` (fichero propio):
   - `parse_config` / `render_config` idempotentes: conservan secciones desconocidas y no
     pierden `<system>`, `<interfaces>`, `<filter>`, `<nat>`.
   - `assign()` con interfaz inexistente devuelve error con los nombres disponibles.
   - `rule()` inserta la regla **antes** de un `reject` existente.
   - `run()` enmascara la contraseña en stdout/stderr (doble de `sshpass` mediante monkeypatch).
   - `from_env()` lee nombres de variables y falla con el nombre de la que falta.
   - `detect_ifnames()` para `e1000` → `em0/em1`, para `virtio-net-pci` → `vtnet0/1`.
3. `tests/test_mcp_speed.py` (fichero propio):
   - `gns3_batch` con 5 operaciones de solo lectura mantiene el orden de `results` por índice
     y reporta `parallel=True` y `wall_ms` entero.
   - una operación conerror no rompe las demás.
   - operaciones con efecto secundario no se paralelizan (verificar que el flag lo refleja).
4. `tests/test_cli_pf.py` (fichero propio): `pf detect` sin credenciales, `pf status` sin
   `PFSENSE_PASSWORD` devuelve el error con el nombre de la variable y no imprime el valor.

Si los símbolos no existen al escribir los tests, usa `pytest.mark.skipif` con razón explícita
contra el contrato; al mergear se activarán.

## Prohibido

No edites `gns3core.py`, `pfsense.py`, `gns3_mcp_server.py`, `cli/gns3lab`, `docs/`,
`README.md` ni `PROJECT.md`. No toques `tests/test_drift.py`, `tests/test_batch.py` ni otros
ficheros de tests existentes. Si un test destapa un bug, `xfail(strict=True, reason="BUG: …")`
y descríbelo. No `git push`, no PR, no cambio de rama.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-pftests
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q --cov=gns3core --cov=pfsense --cov-report=term-missing --cov-fail-under=90
```

Pega las últimas 15 líneas con cobertura y total de tests (skips incluidos).

Commit: `test: integración pfSense nativa y batch paralelo sin servidor`. Informa de números y bugs.
