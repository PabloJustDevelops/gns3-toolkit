# BRIEF — carril `guimcp` (portar la GUI al MCP)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-guimcp` · rama `opencode/guimcp` (no cambies).

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
**No los reimplementes**: llámalos desde el núcleo.

Lee `AGENTS.md`, `PROJECT.md`, `gns3core.py`, `gns3_mcp_server.py` y el inventario
`orchestration/inventario-rutas-gns3.txt`.

## Contrato (idéntico en el carril CLI; no lo cambies)

| Necesidad GUI | Tool MCP |
|---|---|
| Resize disk | ampliar `gns3_node_edit` con `action="disk-resize"`, parámetro `size` |
| Reset consola / URL WS | `gns3_console_control(node, action="reset\|url")` |
| Duplicar/cargar proyecto | ampliar `gns3_project_io` con `action="duplicate\|load"` |
| Stats del proyecto | `gns3_project_stats(project_id, project_name)` |
| Ficheros del proyecto | `gns3_project_files(action="get\|put", path, content, ...)` |
| Computes | ampliar `gns3_compute` con `action="info\|list\|add\|update\|delete\|ports\|idlepc\|call"` |
| GNS3 VM | `gns3_gns3vm(action="show\|set\|engines\|vms", engine, body)` |
| Notificaciones | `gns3_notifications(project_id=None, project_name=None)` |
| Plantillas | ampliar `gns3_template` con `action="duplicate\|base-config"` |
| Símbolos | ampliar `gns3_symbols` con `action="list\|dimensions\|raw\|default\|upload"` |
| Licencia IOU | `gns3_iou_license(action="get\|set", body=None)` |
| Servidor | `gns3_server(action="shutdown\|reload\|debug\|version")` con `confirm=True` obligatorio |
| Emuladores | `gns3_emulator(action="qemu-binaries\|qemu-capabilities\|docker-images\|interfaces\|ports\|udp", port=None)` |
| Filtros de enlace | ampliar `gns3_links` con `action="filters"` |
| Enlaces/idlepc de nodo | ampliar `gns3_node_edit` con `action="links\|idlepc"` |

Reglas: tools devuelven datos, no imprimen; errores como `{"error": "..."}` con mensaje
interno; firmas con tipos simples para fastmcp; todo antes de `if __name__ == "__main__"`.
Las acciones destructivas exigen `confirm=True`; sin él devuelven un error explícito.

**Prohibido ejecutar contra el servidor real** `shutdown`, `reload`, compute delete/update,
`iou_license set` ni resize_disk. Verifícalas con el flag y un doble, no contra GNS3.

## Prohibido

No edites `gns3core.py`, `cli/gns3lab`, `tests/`, `docs/`, `README.md` ni `PROJECT.md`.
No `git push`, no PR, no cambio de rama. No crees ni borres proyectos.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-guimcp
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile gns3_mcp_server.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python - <<'EOF'
import asyncio, sys
sys.path.insert(0, ".")
import gns3_mcp_server as s
t = asyncio.run(s.mcp.list_tools())
print("tools:", len(t), sorted(x.name for x in t))
print("gns3vm:", str(s.gns3_gns3vm())[:180])
print("emulator:", str(s.gns3_emulator(action="qemu-capabilities"))[:160])
print("project stats:", str(s.gns3_project_stats(project_name="examen-kit"))[:160])
print("shutdown sin confirm:", s.gns3_server(action="shutdown"))
EOF
```

Commit: `feat(mcp): GUI operativa portada a tools`. Informa del número de tools y salida real.
