# BRIEF — carril `mcp` (paridad total del servidor MCP)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-mcp` · rama `opencode/mcp` (no cambies).

## Contexto

`gns3_mcp_server.py` tiene hoy 20 tools. `gns3core.py` acaba de ampliarse con la superficie
completa de la API v2 (`computes`, `compute`, `statistics`, `symbols`, `appliances`, `images`,
`project_get/close/delete`, `template_get/update/delete`, `node_action`, `node_command_line`,
`link_update/link_delete/link_capture`, `drawing_update/drawing_delete`, `snapshots`,
`snapshot_create/restore/delete`, `drawings`, `drawing_create`, `compute_write_file`).
**Úsalos desde el núcleo; no reimplementes peticiones HTTP.**

Lee también `AGENTS.md`, `PROJECT.md`, `gns3core.API_V2_MAP` y las tools existentes.

## Contrato de nombres (idéntico en el carril CLI; no lo cambies)

| Necesidad | Tool MCP |
|---|---|
| Compute | `gns3_compute(cid="local")` |
| Estadísticas | `gns3_statistics()` |
| Símbolos | `gns3_symbols(pattern=None)` |
| Appliances | `gns3_appliances(pattern=None)` |
| Acción de nodo | `gns3_node_action(node, action, project_id=None, project_name=None)` con `action=start\|stop\|reload\|suspend` |
| Línea de comandos del nodo | `gns3_command_line(node, project_id=None, project_name=None)` |
| Editar enlace | ampliar `gns3_links` con `action="update"`, `link_id` y `filters` |
| Editar nota | ampliar `gns3_drawings` con `action="update"`, `drawing_id`, `x`, `y`, `text`, `color` |
| Captura | ampliar `gns3_capture` con `file_name` (rutas del núcleo `link_capture`) |

Las tools de projects, templates, snapshots, node_files, monitor, exec y project_io ya
existen: **comprueba que cubren todas las operaciones del mapa** y añade solo lo que falte.

Reglas: tools devuelven datos y no imprimen; errores como `{"error": "..."}` con mensaje
interno; firmas con tipos simples para que fastmcp genere schema válido; todo antes de
`if __name__ == "__main__": mcp.run()`.

## Prohibido

- **No edites** `gns3core.py`, `cli/gns3lab`, `tests/`, `docs/`, `README.md` ni `PROJECT.md`.
- No `git push`, no PR, no cambio de rama. No crees ni borres proyectos. Si arrancas/paras
  nodos de `examen-kit`, devuélvelos a su estado.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-mcp
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile gns3_mcp_server.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python - <<'EOF'
import asyncio, sys
sys.path.insert(0, ".")
import gns3_mcp_server as s
tools = asyncio.run(s.mcp.list_tools())
print(len(tools), sorted(t.name for t in tools))
print("compute:", str(s.gns3_compute())[:200])
print("stats:", str(s.gns3_statistics())[:200])
print("symbols:", len(s.gns3_symbols(pattern="router")))
print("appliances:", len(s.gns3_appliances(pattern="pfsense")))
EOF
```

Meta: **≥25 tools** y las 8 áreas de `API_V2_MAP` cubiertas.

Commit en tu rama con mensaje `feat(mcp): paridad total con la API v2`. Informa del número
de tools, de la salida de los gates y de cualquier tool que la API rechazara (status y mensaje).
