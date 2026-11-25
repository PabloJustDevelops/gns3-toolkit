# BRIEF — carril `niomcp` (NIO, capturas por puerto y eventos en el MCP)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-niomcp` · rama `opencode/niomcp`.

## Contexto

El núcleo ya tiene (no los reimplementes): `port_nio`, `port_capture`, `nodes_action`,
`nodes_console_reset`, `node_action` con `resume|pause|unpause`, `qemu_img_binaries`,
`qemu_img_config`, `virtualbox_vms`, `vmware_vms`, `vmware_vmnet`, `notifications_ws_url`,
`v1_version`. Lee `AGENTS.md`, `PROJECT.md`, `gns3core.py`, `gns3_mcp_server.py` y
`docs/research/ubridge-console-enganche.md`.

## Contrato (idéntico en el carril CLI)

| Necesidad | Tool MCP |
|---|---|
| NIO de puerto | `gns3_nio(node, adapter, port, action="get\|set\|delete", nio=None, emulator=None, project_id=None, project_name=None)` |
| Captura por puerto | `gns3_port_capture(node, adapter, port, action="start\|stop\|pcap", file_name=None, emulator=None, project_id=None, project_name=None)` |
| Acciones nodo extra | verificar que `gns3_node_action` acepta `resume|pause|unpause` (el núcleo ya lo hace) |
| Acción masiva | `gns3_nodes_bulk(action="start\|stop\|suspend\|reload", project_id=None, project_name=None, confirm=False)` |
| Reset de consolas | ampliar `gns3_console_control` con `action="reset-all"`, `confirm=False` |
| Imágenes qemu / VMs | ampliar `gns3_emulator` con `action="img-binaries\|img-config\|virtualbox-vms\|vmware-vms\|vmware-vmnet"`, `body=None`, `confirm=False` |
| Eventos WS | `gns3_events_url(project_id=None, project_name=None)` → la URL y una nota de cómo suscribirse; si se puede con `websockets` (ya en el venv), `gns3_events(action="url\|listen", seconds=5)` devolviendo eventos reales con timeout estricto |
| Versión v1 | ampliar `gns3_status` con el campo `version_v1` usando `v1_version()` |

Los errores del compute (incluido un 500 con traceback) se devuelven como
`{"error": "...", "status": N}` sin inventar contenido. Las acciones disruptivas exigen
`confirm=True`; sin él devuelven error explicando cómo confirmar.

## Prohibido

No edites `gns3core.py`, `cli/gns3lab`, `tests/`, `docs/`, `README.md` ni `PROJECT.md`.
No `git push`, no PR, no cambio de rama. **No ejecutes acciones masivas, reset-all,
img-config, nio set/delete ni capturas contra el servidor real.**

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-niomcp
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile gns3_mcp_server.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python - <<'EOF'
import asyncio, sys
sys.path.insert(0, ".")
import gns3_mcp_server as s
t = asyncio.run(s.mcp.list_tools())
print("tools:", len(t), sorted(x.name for x in t))
print("events url:", str(s.gns3_events_url())[:140])
print("emulator:", str(s.gns3_emulator(action="img-binaries"))[:150])
print("bulk sin confirm:", s.gns3_nodes_bulk(action="stop", project_name="examen-kit"))
EOF
```

Commit: `feat(mcp): NIO/captura por puerto, acciones masivas y eventos WS`. Informa de tools y salida.
