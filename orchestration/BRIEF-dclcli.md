# BRIEF — carril `dclcli` (subcomando `gns3lab lab`)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-dclcli` · rama `opencode/dclcli`.

## Contexto

`scripts/labspec.py` ya trae `validate|plan|apply|verify` y el carril `dclcore` añade
`export` y `diff` con el contrato de `orchestration/BRIEF-dclcore.md`. Lee `AGENTS.md`,
`cli/gns3lab` (handlers en `main()` ≈4697, `cmd_pf` ≈4116, `cmd_verify` ≈4185) y ese brief.

**Importante**: en la CLI ya existe `export` (exportar proyecto `.gns3project`). Por eso el
nuevo subcomando se llama **`lab`**, no `export`.

## Contrato

`gns3lab lab <acción> [opciones] [--json]` con seis acciones:

| Acción | Ejemplo | Delegado en `labspec` |
|---|---|---|
| `validate` | `gns3lab lab validate --spec examples/lab-ejemplo.yaml` | `validar` |
| `plan` | `gns3lab lab plan --spec …` | `ordenes` |
| `diff` | `gns3lab lab diff --spec … --topology topo.json` | `diff` |
| `apply` | `gns3lab lab apply --spec … --yes` | `aplicar_deseado` |
| `verify` | `gns3lab lab verify --spec …` | `verificar` |
| `export` | `gns3lab lab export --project <nombre> --out lab.yaml` | `export` sobre la topología leída con `gns3core.Client` |

Requisitos:
- `--json` global (ya existe en la CLI) produce un objeto con `ok`, `action` y `data` para
  todas las acciones; en `apply` sin `--yes` devuelve `ok=False` y el plan, sin escribir.
- `export` obtiene la topología con `gns3core.Client` (nodos y enlaces, ya existen helpers),
  llama a `labspec.export` y escribe YAML con `yaml.safe_dump(sort_keys=False)` en `--out`
  (o stdout si no se da). **Solo lectura del servidor salvo la escritura local de `--out`.**
- `diff` y `export` funcionan con `--topology <fichero.json>` para ser probables sin servidor.
- La ayuda en español; `cmd_lab` junto a `cmd_pf`/`cmd_verify`; registrar en `handlers` y, si
  hace falta, en `needs_core` (export sí lo necesita; validate/plan/diff no).
- No uses `sys.path`全球; la CLI ya añade la raíz del repo. Importa `scripts.labspec` con
  `importlib` o añade `scripts/` al path de forma explícita, y documenta por qué.

## Prohibido

No edites `scripts/labspec.py`, `gns3core.py`, `gns3_mcp_server.py`, `tests/`, `docs/`,
`README.md` ni `PROJECT.md`. No `git push`, no PR, no cambio de rama. No ejecutes `apply`
contra un servidor real; las pruebas son `--help`, `validate`, `plan`, `diff` y `export`
con ficheros locales.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-dclcli
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile cli/gns3lab
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab lab --help | head -10
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab lab validate --spec examples/lab-ejemplo.yaml --json
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab lab plan --spec examples/lab-ejemplo.yaml --json | head -12
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab lab apply --spec examples/lab-ejemplo.yaml 2>&1 | tail -2
```

Commit: `feat(cli): subcomando lab declarativo`. Informa de salida real.
