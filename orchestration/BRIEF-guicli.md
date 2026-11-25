# BRIEF — carril `guicli` (portar la GUI a la CLI)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-guicli` · rama `opencode/guicli` (no cambies).

## Contexto

`gns3core.py` ya tiene los métodos de la GUI operativa (leídos del código de `gns3server`):
`node_resize_disk`, `console_reset`, `console_ws_url`, `node_links`, `node_idlepc`,
`link_available_filters`, `project_stats`, `project_duplicate`, `project_load`,
`project_file_read/write`, `compute_create/update/delete/ports/auto_idlepc/action`,
`gns3vm/gns3vm_update/gns3vm_engines/gns3vm_vms`, `notifications`,
`template_duplicate/template_base_configs/template_base_config`,
`symbol_dimensions/symbol_raw/symbol_raw_upload/default_symbols`,
`iou_license/iou_license_update`, `server_shutdown/server_reload/server_debug`,
`qemu_binaries/qemu_capabilities/docker_images/network_interfaces/network_ports/udp_port`.
**No los reimplementes**: llámalos.

Lee `AGENTS.md`, `PROJECT.md`, `gns3core.py`, `cli/gns3lab` y el inventario real de rutas
`orchestration/inventario-rutas-gns3.txt`.

## Contrato (idéntico en el carril MCP; no lo cambies)

| Operación GUI | Comando CLI |
|---|---|
| Resize disk | `gns3lab node disk-resize <nodo> --size <GB> [-p PROY]` |
| Reset consola / URL WS | `gns3lab console reset <nodo>` y `gns3lab console url <nodo>` |
| Duplicar proyecto | `gns3lab project duplicate <nombre> [-p PROY]` |
| Cargar proyecto | `gns3lab project load <ruta>` |
| Stats del proyecto | `gns3lab project stats [-p PROY] [--json]` |
| Ficheros del proyecto | `gns3lab project file get|put <ruta> [--content TEXTO]` |
| Administrar computes | `gns3lab compute add|update|rm|ports|idlepc|action ...` |
| GNS3 VM | `gns3lab gns3vm show|set|engines|vms ...` |
| Notificaciones | `gns3lab notify [proyecto] [--json]` |
| Duplicar plantilla / base-config | `gns3lab template duplicate|base-config ...` |
| Símbolos | `gns3lab symbol dimensions|raw|default|upload <id> ...` |
| Licencia IOU | `gns3lab iou-license get|set ...` |
| Servidor | `gns3lab server shutdown|reload|debug --yes` |
| Emuladores | `gns3lab emulator qemu-binaries|qemu-capabilities|docker-images|interfaces|ports|udp ...` |
| Filtros de enlace | `gns3lab link filters <link_id> [-p PROY]` |
| Enlaces/idlepc de nodo | `gns3lab node links|idlepc <nodo> [-p PROY]` |

Reglas del fichero: ayuda en español, errores por `_err(body)`, comandos en `handlers` y
`needs_core`, `--json` en los informativos. Si una acción es destructiva (`server shutdown`,
`server reload`, `compute rm`, `project duplicate`), exige `--yes` o confirmación por TTY.

**Prohibido ejecutar contra el servidor real** `server shutdown`, `server reload`, `compute
rm/update`, `iou-license set` ni `resize_disk` (podrían tumbar o dañar el lab). Esos comandos se
verifican con `--help` y con un doble; los demás sí con el servidor en lectura.

## Prohibido

No edites `gns3core.py`, `gns3_mcp_server.py`, `tests/`, `docs/`, `README.md` ni `PROJECT.md`.
No `git push`, no PR, no cambio de rama. No crees ni borres proyectos del servidor.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-guicli
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile cli/gns3lab
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab --help | head -1 | tr ',' '\n' | wc -l
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab gns3vm show | head -6
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab emulator qemu-capabilities | head -4
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab project stats -p examen-kit
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab symbol dimensions ':/symbols/cloud.svg' | head -4
```

Commit: `feat(cli): GUI operativa portada a comandos`. Informa de comandos añadidos y salida real.
