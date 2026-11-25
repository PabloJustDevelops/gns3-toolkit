# BRIEF — carril `extests` (tests de resources, prompts y comando examen)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-extests` · rama `opencode/extests`.

## Contexto

`gns3core.py` tiene 718 sentencias al 100 % (456 tests). En paralelo se están añadiendo:

- resources MCP: `gns3://status`, `gns3://projects`, `gns3://project/{project}/topology`,
  `gns3://templates` y prompts `gns3-diagnostico`, `gns3-examen` (carril `mcpres`);
- comando `gns3lab examen setup|verify|reset` (carril `examcli`).

## Objetivo

1. Mantener **100 % de cobertura de `gns3core.py`** (`--cov=gns3core --cov-fail-under=100`).
   Si el núcleo no cambia, basta con verificar que sigue en 100 % (456 tests).
2. Añadir tests que, **sin servidor GNS3**, comprueben los contratos de resources y prompts:
   que los cuatro URIs y los dos nombres existen, que un proyecto inexistente devuelve error
   con los nombres disponibles, que los prompts no contienen credenciales ni rutas de usuario.
   Usa los dobles de `tests/conftest.py` y una llamada directa a las funciones registradas.
3. Añadir un test del contrato de `gns3lab examen`: que `verify --json` produce un JSON con
   `ok` y `problems`, y que `reset` sin `--yes` se niega. Puede invocar el módulo de la CLI
   con un `Namespace` falso y un servidor doble, sin tocar el real.

Si los otros carriles aún no han mergeado sus ficheros, escribe los tests contra el contrato
literal de los briefs (`BRIEF-mcpres.md`, `BRIEF-examcli.md`) y márcalos con
`pytest.mark.skipif` hasta que el símbolo exista, con una razón explícita.

## Prohibido

No edites `gns3core.py`, `gns3_mcp_server.py`, `cli/gns3lab`, `docs/` ni `PROJECT.md`.
Si un test destapa un bug, `xfail(strict=True, reason="BUG: ...")` y descríbelo.
No `git push`, no PR, no cambio de rama.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-extests
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q --cov=gns3core --cov-report=term-missing --cov-fail-under=100
```

Pega las últimas 15 líneas con cobertura y total de tests.

Commit: `test: resources/prompts y comando examen sin servidor`. Informa de números y bugs.
