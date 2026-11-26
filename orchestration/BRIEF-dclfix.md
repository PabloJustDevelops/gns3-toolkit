# BRIEF — carril `dclfix` (cinco fallos reales hallados por revisión independiente)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-dclfix` · rama `opencode/dclfix`.

## Contexto

La integración declarativa ya está en `master` (HEAD actual). Codex `sol 6.2 medium` revisó
el diff y encontró cinco fallos. **Todos han sido contrastados contra el código por Hermes**;
son reales. Corrígelos sin reabrir decisiones ni cambiar el diseño general. Lee `AGENTS.md`,
`scripts/labspec.py`, `cli/gns3lab` (subcomando `lab`), `gns3_mcp_server.py` (`gns3_lab`) y
`docs/LAB-SPEC.md`.

## Correcciones

1. **MCP con servidor ajeno** (`gns3_mcp_server.py`, `_gns3_lab_action`): `actual` se lee del
   servidor configurado en el MCP pero `server` se pasa a las órdenes escritas. En `apply`, si
   `server` está definido, devuelve error claro: `gns3_lab apply solo opera en el servidor del
   MCP; usa gns3lab lab apply --server para otro`. En `validate|plan|diff|export` se mantiene.
2. **Credenciales en errores anidados** (`_lab_action_error`): hoy solo redacta valores `str`
   en `extra`; un `detail` con diccionario anidado puede filtrar user/password de una URL.
   Añade `_lab_redact_any(value)` recursivo (str → `_lab_redact`, dict/list/tuple → recursivo,
   otros → tal cual) y úsalo para todo `extra`.
3. **`up` arranca nodos fuera de la spec** (`scripts/labspec.py`, `plan`): hoy siempre añade
   `["up", proyecto]`, lo que arranca nodos parados no declarados. Añade `up` **solo** cuando
   `actual` no tiene `project` (proyecto nuevo). Si el proyecto ya existía, no arranca nada.
4. **CLI `lab apply` no es idempotente** (`cli/gns3lab`): hoy `actual` es `None` salvo
   `--topology` y el plan se calcula con `ordenes(deseado)` (proyecto siempre ausente).
   Añade `--topology` al parser de `apply` y, si no se da, obtiene la topología real con
   `gns3core.Client` y `labspec.export` (misma vía que `lab export`); si el proyecto no existe,
   usa `{}`. Calcula el plan con `labspec.plan(deseado, actual, server)` y muéstralo en el
   `--json`/plan impreso. Sin `--yes` sigue sin escribir.
5. **`export` pierde el puerto del enlace** (`scripts/labspec.py`): hoy solo guarda
   `adapter_number`. Extiende el esquema v1 con `porta`/`portb` **opcionales** en cada link;
   `export` los rellena cuando `port_number` no es 0; `diff` los compara; `plan` pasa
   `--ppa/--ppb` a `link add` cuando existen. Los specs antiguos sin puertos siguen válidos
   y siguen significando puerto 0. Actualiza `docs/LAB-SPEC.md`, `docs/LAB-DECLARATIVO.md`
   y `skill-sync/references/lab-declarativo.md` con los dos campos nuevos.

## Tests

Actualiza `tests/test_labspec_diff.py`, `tests/test_cli_lab.py` y `tests/test_mcp_lab.py`
(ficheros ya existentes) con un caso por corrección: `plan` sin `up` en proyecto existente,
links con `porta/portb` en export/diff/plan, `lab apply --topology` idempotente, `apply` con
`server` rechazado, y `_lab_action_error` con `detail` anidado sin filtrar la password de
`GNS3_PASSWORD` (doble en entorno, valor falso, nunca real).

## Prohibido

No edites `gns3core.py`, `pfsense.py`, `README.md`, `PROJECT.md`, `tests/test_mcp_optimization.py`
ni `orchestration/`. No `git push`, no PR, no cambio de rama. No ejecutes `apply` con `yes`
contra un servidor real: usa `--topology` local y dobles.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-dclfix
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile scripts/labspec.py cli/gns3lab gns3_mcp_server.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q tests/test_labspec_diff.py tests/test_cli_lab.py tests/test_mcp_lab.py tests/test_mcp_optimization.py
python3 scripts/verify.py
python3 scripts/check-links.py
```

Commit: `fix(spec): cinco fallos de idempotencia, redacción y export de puertos`. Informa de
salida real y de cada corrección con fichero:línea.
