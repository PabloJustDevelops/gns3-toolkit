# BRIEF — carril `pfcli` (comandos pfSense en la CLI)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-pfcli` · rama `opencode/pfcli`.

## Contexto

La CLI ya tiene 45 comandos, pero configurar pfSense sigue siendo un proceso manual. El módulo
`pfsense.py` lo crea otro carril con la API descrita en `orchestration/BRIEF-pfcore.md`.
Lee `AGENTS.md`, `PROJECT.md`, `cli/gns3lab` y ese brief.

## Contrato

`gns3lab pf <acción> [opciones] [--json]`:

| Acción | Ejemplo | Método delegado |
|---|---|---|
| `detect` | `gns3lab pf detect -p examen-kit` | `detect_ifnames(node)` — solo lee el nodo GNS3, sin SSH |
| `status` | `gns3lab pf status` | `PfSense.from_env().status()` |
| `config get\|put` | `gns3lab pf config get > fw.xml` / `pf config put fw.xml` | `get_config()` / `put_config()` |
| `assign` | `gns3lab pf assign --wan em0 --lan em1 [--opt1 vtnet2]` | `assign(mapping)` |
| `ip` | `gns3lab pf ip em1 192.168.10.1 24 [--gw …]` | `set_ip()` |
| `dhcp` | `gns3lab pf dhcp em1 192.168.10.100 192.168.10.200 [--dns …]` | `dhcp()` |
| `rule` | `gns3lab pf rule pass --if lan --proto tcp --src any --dst any --port 80` | `rule()` |
| `nat` | `gns3lab pf nat --if wan` | `nat()` |
| `ssh` | `gns3lab pf ssh --port 22022` | `enable_ssh()` |

Requisitos:
- `--json` (local en este subcomando) devuelve un objeto parseable con `ok` y `data`.
- Credenciales **solo** de entorno (`PFSENSE_HOST`, `PFSENSE_USER`, `PFSENSE_PASSWORD`,
  `PFSENSE_PORT`). Si falta `PFSENSE_PASSWORD`, error con el nombre de la variable, sin valor.
- `detect` funciona sin credenciales y sin SSH: usa `gns3core.Client` para leer el nodo del
  proyecto (`pfSense` por nombre, o `--node`), y `detect_ifnames`.
- `config put` exige `--yes` si el fichero no viene de `config get` en la misma sesión; nunca
  sobrescribe `/conf/config.xml` sin backup (el método ya lo hace).
- La ayuda en español y el docstring de `main()` incluyen el nuevo comando.

## Prohibido

No edites `gns3core.py`, `pfsense.py`, `gns3_mcp_server.py`, `tests/`, `docs/`, `README.md` ni
`PROJECT.md`. No `git push`, no PR, no cambio de rama. **No ejecutes acciones SSH reales**
contra pfSense; verifica con `--help` y con `pf detect` (que no usa SSH).

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-pfcli
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile cli/gns3lab
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab pf --help | head -8
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab pf detect -p examen-kit --json | head -8
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab pf status 2>&1 | head -3
```

Commit: `feat(cli): comandos pf nativos`. Informa de salida real.
