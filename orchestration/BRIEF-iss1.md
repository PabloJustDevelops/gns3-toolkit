# BRIEF — carril `iss1` (issue #1: errores HTTP silenciados)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-iss1` · rama `opencode/iss1`.

## Contexto

El issue #1 del repo pide eliminar los falsos «no hay nada» cuando la API falla. Parte ya está
arreglada (plantillas en PR #2/#5, `lab export`); quedan las otras consultas de `gns3core.Client`
que devuelven `[]` con HTTP 500: `links()`, `qemu_images()`, `computes()`, `symbols()`,
`appliances()`, `images()`, `snapshots()`, `drawings()`. Lee `AGENTS.md`, `gns3core.py`,
`cli/gns3lab` y `gns3_mcp_server.py`.

## Contrato

1. **No cambiar el comportamiento por defecto del núcleo** (hay 100 % de cobertura y muchos
   tests esperan `[]`). Añade una variante explícita: `json_list_or_die(path, what)` (o un flag
   `strict` opcional) que lance `RuntimeError(f"{what}: [{st}] {body}")` si el status no es 200
   o el cuerpo no es lista.
2. Usa esa variante en los **call sites que toman decisiones**: lectura de enlaces en
   `cmd_link`/`cmd_examen` y en `gns3_links`/`gns3_drawings`/`gns3_snapshots`/`gns3_images`/
   `gns3_symbols`/`gns3_appliances`. Los comandos de solo listado pueden mantener `[]`, pero
   deben distinguir «sin enlaces» de «no se pudo leer» cuando falla la API.
3. Tests nuevos `tests/test_silent_errors.py` con `FakeApi` (existe en `tests/conftest.py`):
   HTTP 500 en cada familia → error literal con `[500]`, nunca «no encontrado» / `[]` silencioso.
4. No tocar `pfsense.py`, `captures.py`, `webui_capture.py`.

## Gates

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-iss1
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q tests/test_silent_errors.py tests/test_batch.py tests/test_mcp_optimization.py
python3 scripts/verify.py
```

## Entrega

Commit en `opencode/iss1`, push y `gh pr create ... --body "... Closes #1 ..."`, **sin mergear**.
Si el harness niega el push, dilo en una línea y espera: Hermes publica.
