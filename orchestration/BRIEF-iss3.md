# BRIEF — carril `iss3` (issue #3: skipif obsoletos)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-iss3` · rama `opencode/iss3`.

## Contexto

El issue #3 documenta trampas silenciosas en el propio banco de tests: hay `skipif` con razones
«falta X» donde X ya existe. Si una refactorización elimina X, el test se omite en vez de
fallar. Lee `AGENTS.md` y los ficheros citados en el issue.

## Contrato

1. Eliminar los `skipif` obsoletos de: `tests/test_exam_cli.py`, `tests/test_mcp_resources.py`,
   `tests/test_batch.py`, `tests/test_cli_json.py`, `tests/test_mcp_speed.py`,
   `tests/test_cli_pf.py`, `tests/test_pfsense.py`, `tests/test_cli_lab.py`,
   `tests/test_labspec_diff.py`, `tests/test_mcp_lab.py`. Comprobar uno a uno que el símbolo
   existe en el código antes de quitar el marcad&oacute; (sin borrar tests).
2. Convertir los que aún tengan sentido en aserciones de contrato
   (`assert hasattr(...)` / `assert name in TOOLS_CONTRATO`), para que fallen si el símbolo
   desaparece.
3. Actualizar `orchestration/COMPONENTES-CANDIDATOS.md:88`, donde el componente 5 sigue
   «pendiente en CLI».
4. **No tocar** `gns3core.py`, `pfsense.py`, `cli/gns3lab`, `gns3_mcp_server.py`, `README.md`
   ni `PROJECT.md`. Solo tests, el fichero de componentes y, si hace falta, un test de contrato
   nuevo.

## Gates

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-iss3
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q
python3 scripts/verify.py
python3 scripts/check-links.py | tail -1
```

Cuenta los tests antes y después: no debe bajar el total.

## Entrega

Commit en `opencode/iss3`, push y `gh pr create ... --body "... Closes #3 ..."`, **sin mergear**.
Si el harness niega el push, dilo en una línea y espera: Hermes publica.
