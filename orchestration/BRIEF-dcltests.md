# BRIEF — carril `dcltests` (tests de export/diff, CLI lab y resources)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-dcltests` · rama `opencode/dcltests`.

## Contexto

Los carriles `dclcore`, `dclcli` y `dclmcp` añaden `export`, `diff`, `plan` idempotente,
`gns3lab lab` y tres resources más una tool. Contratos en `orchestration/BRIEF-dclcore.md`,
`BRIEF-dclcli.md` y `BRIEF-dclmcp.md`. Lee `AGENTS.md`, `tests/conftest.py` y esos briefs.

Hoy hay 737 tests y 100 % de cobertura de `gns3core.py`. Hay que mantenerlo y cubrir lo nuevo
sin servidor ni SSH.

## Objetivo (ficheros propios, no toques los existentes)

1. `tests/test_labspec_diff.py`:
   - `export(topo)` produce un spec que pasa `validar` sin errores; omite enlaces rotos y los
     reporta en `warn`; nunca inventa `ip`/`expect`.
   - `diff(deseado, actual)` detecta nodos y enlaces nuevos y sobrantes; `diff(s,s).sin_cambios`
     es `True`; `plan(s,s)` es vacío.
   - `aplicar_deseado` sin `yes` devuelve 2 y **no llama** a `ejecutar` (monkeypatch).
   - `aplicar_deseado` con `yes` llama a las órdenes en orden y para en el primer fallo.
2. `tests/test_cli_lab.py`: `lab --help` incluye las seis acciones; `lab validate --json` sobre
   `examples/lab-ejemplo.yaml` da `ok=True`; `lab apply` sin `--yes` no ejecuta nada; `lab diff`
   con `--topology` local no habla con el servidor; orden de `handlers` intacto.
3. `tests/test_mcp_lab.py`: `list_resources()` incluye `gns3://lab/desired|actual|diff`;
   `list_tools()` crece en uno; `gns3_lab(action="apply")` sin `yes` no escribe;
   `gns3_lab(action="diff", topology=...)` funciona sin `GNS3_LAB_SPEC`; sin esa variable,
   el resource `desired` devuelve error con `hint`.

Si un símbolo no existe aún, usa `pytest.mark.skipif` con razón que cite el contrato; al
mergear se activarán. Si un test destapa un bug, `xfail(strict=True, reason="BUG: …")` y
descríbelo. No edites tests existentes.

## Prohibido

No edites `gns3core.py`, `scripts/labspec.py`, `gns3_mcp_server.py`, `cli/gns3lab`, `docs/`,
`README.md` ni `PROJECT.md`. No `git push`, no PR, no cambio de rama.

## Gate (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-dcltests
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q --cov=gns3core --cov=scripts.labspec --cov-report=term-missing --cov-fail-under=90
```

Pega las últimas 15 líneas con cobertura y total de tests (skips incluidos).

Commit: `test: laboratorio declarativo export/diff y resources`. Informa de números y bugs.
