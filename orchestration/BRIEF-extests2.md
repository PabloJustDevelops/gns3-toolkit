# BRIEF — carril `extests2` (tests de batch, informe y --json global)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-extests2` · rama `opencode/extests2`.

## Contexto

En paralelo se están añadiendo `gns3_batch` y `gns3_informe` en el MCP (carril `batchmcp`) y
`--json` global más `examen informe` en la CLI (carril `jsoncli`). Hay que cubrirlos con tests
sin servidor GNS3. Lee `AGENTS.md`, `PROJECT.md`, `tests/conftest.py`, los briefs
`BRIEF-batchmcp.md` y `BRIEF-jsoncli.md`.

## Objetivo

1. Mantener **100 % de cobertura de `gns3core.py`** (`--cov=gns3core --cov-fail-under=100`).
2. `tests/test_batch.py` (fichero propio; **no toques** `tests/test_drift.py`, de otro carril):
   - `gns3_batch` con dos operaciones de solo lectura sobre los dobles: resultados indexados,
     `total_ms` entero y `ok` correcto.
   - error en una operación no detiene las demás; con `stop_on_error=True` sí.
   - más de 20 operaciones → error explícito.
   - tool destructiva sin `confirm` → bloqueada con mensaje claro; con `confirm` → se ejecuta
     sobre el doble.
   - `gns3_informe` devuelve path, bytes y contenido; el contenido no incluye credenciales del
     config ni rutas de otro usuario; un dato ilegible se refleja como error literal.
3. Tests del `--json` global de la CLI con un handler falso: JSON válido se pasa tal cual; texto
   se envuelve en `{"cmd","ok","output"}`; el exit code se conserva; `stderr` no se captura.

Si los símbolos aún no existen cuando escribas los tests, usa `pytest.mark.skipif` con razón
explícita contra el contrato de los briefs. Cuando el padre mergee, los tests se activarán.

## Prohibido

No edites `gns3core.py`, `gns3_mcp_server.py`, `cli/gns3lab`, `tests/test_drift.py`,
`docs/` ni `PROJECT.md`. Si un test destapa un bug, `xfail(strict=True, reason="BUG: ...")` y
descríbelo. No `git push`, no PR, no cambio de rama.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-extests2
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q --cov=gns3core --cov-report=term-missing --cov-fail-under=100
```

Pega las últimas 15 líneas con cobertura y total de tests (skips incluidos).

Commit: `test: batch, informe y salida JSON uniforme sin servidor`. Informa de números y bugs.
