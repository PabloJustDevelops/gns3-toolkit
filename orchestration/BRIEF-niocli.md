# BRIEF — carril `niocli` (NIO, capturas por puerto y acciones masivas en CLI)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-niocli` · rama `opencode/niocli`.

## Contexto

El núcleo ya tiene (no los reimplementes): `port_nio`, `port_capture`, `nodes_action`,
`nodes_console_reset`, `node_action` (ahora con `resume|pause|unpause`), `qemu_img_binaries`,
`qemu_img_config`, `virtualbox_vms`, `vmware_vms`, `vmware_vmnet`, `notifications_ws_url`,
`v1_version`. `API_V2_MAP` tiene 12 áreas. Lee `AGENTS.md`, `PROJECT.md`, `gns3core.py`,
`cli/gns3lab`, `orchestration/inventario-rutas-gns3.txt` y
`docs/research/ubridge-console-enganche.md` (explica por qué NIO es la vía de enganche).

## Contrato (idéntico en el carril MCP)

| Necesidad | Comando CLI |
|---|---|
| NIO de un puerto | `gns3lab nio get\|add\|rm <nodo> --adapter N --port N [--nio JSON] [-p PROY]` |
| Captura por puerto | `gns3lab capture-port <nodo> start\|stop\|pcap --adapter N --port N [-p PROY]` |
| Acciones nodo extra | ampliar `gns3lab node` con `resume\|pause\|unpause` |
| Acción masiva | `gns3lab all start\|stop\|suspend\|reload [-p PROY]` |
| Reset de consolas | `gns3lab console reset-all [-p PROY]` |
| Imágenes qemu | `gns3lab disk binaries\|config [--set clave=valor]` |
| VM invitadas | `gns3lab vm vms\|vmnet [--set clave=valor]` |
| Eventos en vivo | `gns3lab watch [--project] [--seconds N]` — cliente WebSocket por stdlib (handshake + frames), imprime eventos y sale por timeout; si no conecta, imprime la URL de `notifications_ws_url` y el error literal. Nunca se quede colgado. |
| Versión v1 | `gns3lab version-v1` |

`nio` y `capture-port` usan el compute local; si GNS3 devuelve `500` con traceback,
muéstralo tal cual (`_err`), no lo disfraces. `all`, `console reset-all` y `disk config` son
potencialmente disruptivos: exigen `--yes` o confirmación si stdin es TTY.

## Prohibido

No edites `gns3core.py`, `gns3_mcp_server.py`, `tests/`, `docs/`, `README.md` ni `PROJECT.md`.
No `git push`, no PR, no cambio de rama. **No ejecutes `all stop`, `console reset-all`,
`disk config` ni `nio add/rm` contra el servidor real**: verifícalos con `--help` y con el
código. `capture-port` solo en modo `--help` (iniciar captura cambia el estado del lab).

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-niocli
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile cli/gns3lab
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab nio --help | head -6
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab capture-port --help | head -6
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab disk binaries
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab version-v1
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab watch --seconds 2 2>&1 | head -4
```

Commit: `feat(cli): NIO/captura por puerto, acciones masivas y eventos WS`. Informa de la salida.
