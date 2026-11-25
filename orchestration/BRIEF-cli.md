# BRIEF — carril `cli` (paridad total de la CLI)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-cli` · rama `opencode/cli` (no cambies).

## Contexto

`cli/gns3lab` tiene hoy 23 comandos. `gns3core.py` acaba de ampliarse con la superficie
completa de la API v2: `Client.computes()`, `compute()`, `statistics()`, `symbols()`,
`appliances()`, `images()`, `project_get/close/delete()`, `template_get/update/delete()`,
`node_action()`, `node_command_line()`, `link_update/link_delete/link_capture()`,
`drawing_update/drawing_delete()`, `snapshots/snapshot_create/restore/delete()`,
`drawings/drawing_create()`, `compute_write_file()`. **Léelos ahí; no los reimplementes.**

Lee también `AGENTS.md`, `PROJECT.md` y `gns3core.API_V2_MAP`.

## Contrato de nombres (idéntico en el carril MCP; no lo cambies)

| Necesidad | Comando CLI |
|---|---|
| Info de un compute | `gns3lab compute [id] [--json]` |
| Estadísticas | `gns3lab stats [--json]` |
| Símbolos | `gns3lab symbols [--filter TEXTO] [--json]` |
| Appliances | `gns3lab appliances [--filter TEXTO] [--json]` |
| Captura de enlace | `gns3lab capture <link_id> start\|stop\|pcap [-p PROY]` |
| Consola interactiva | `gns3lab console <nodo> [-p PROY]` (stdin, `exit` sale) y `--send "cmd"` no interactivo |
| Acciones de nodo | `gns3lab node start\|stop\|reload\|suspend <nodo> [-p PROY]` |
| Editar enlace | `gns3lab link edit <link_id> --set clave=valor [-p PROY]` |
| Editar/borrar nota | `gns3lab draw edit <drawing_id> --set clave=valor` y `gns3lab draw rm <drawing_id>` |
| Borrar snapshot | `gns3lab snap delete <nombre> [proyecto]` |
| Editar plantilla | `gns3lab template update <nombre> --set clave=valor` |

Reglas del fichero: ayudas en español, errores por `_err(body)` (nunca el schema anidado),
comandos nuevos en `handlers` y en `needs_core` si usan el núcleo, `--json` para salida
parseable en los comandos informativos.

**`console` es la pieza clave contra el VNC**: usa `core.console_for` + `Console.wait_ready()`
y `Console.run()`, con manejo de `EOFError`/`KeyboardInterrupt` para salir limpio. Si el nodo
es VNC, di que use `gns3lab shot|type|key`, igual que hace `exec`.

## Prohibido

- **No edites** `gns3core.py`, `gns3_mcp_server.py`, `tests/`, `docs/`, `README.md` ni
  `PROJECT.md`.
- No `git push`, no PR, no cambio de rama, no crear/borrar proyectos ni nodos del servidor.
  Las pruebas de `capture` y `node` pueden usar `examen-kit`, pero **restaura el estado**
  (si paras un nodo, vuelve a arrancarlo; si inicias una captura, detenla).

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-cli
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile cli/gns3lab
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab --help | head -3
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab compute --json | python3 -m json.tool | head -8
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab stats --json | python3 -m json.tool | head -8
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab symbols --filter router | head -3
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab appliances --filter pfsense | head -3
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab console PC1 --send "show ip" -p examen-kit
```

Commit en tu rama con mensaje `feat(cli): paridad total con la API v2`. Informa de los
comandos añadidos, de la salida de los gates y de cualquier endpoint que rechazara la
petición (mensaje y status literal).
