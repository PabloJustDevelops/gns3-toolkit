# BRIEF — carril `batchmcp` (menos turnos por llamada al MCP)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-batchmcp` · rama `opencode/batchmcp`.

## Contexto

Cada llamada MCP consume un turno del agente. Hoy inspeccionar un lab exige varias llamadas
(`gns3_status`, `gns3_topology`, `gns3_exec`, …). Hay que poder agruparlas y producir un informe
con evidencia real en una sola llamada. Lee `AGENTS.md`, `PROJECT.md`, `gns3_mcp_server.py`
(completo), `gns3core.py` y los resources/prompts existentes.

## Contrato

1. **`gns3_batch(operations: list[dict], stop_on_error: bool = False,
   project_name: str | None = None) -> dict`**
   - Cada operación: `{"tool": "gns3_exec", "args": {...}}`. Se resuelve contra las **funciones
     Python registradas**, no mediante llamadas MCP anidadas.
   - Devuelve `{"ok": bool, "total_ms": int, "results": [{"index", "tool", "ok", "result"|"error", "ms"}]}`.
   - Un error en una operación **no tumba las demás** salvo `stop_on_error=True`.
   - Límite de 20 operaciones; más → error explícito con el mensaje.
   - **Bloquea** tools destructivas (`gns3_server`, `gns3_project_io` con delete/import,
     `gns3_node_edit` con delete, `gns3_node_action` con stop/reload y `gns3_nodes_bulk`) salvo
     que la operación lleve `"confirm": true`. Sin confirmación, devuelve un error claro y sigue.
2. **`gns3_informe(project_name=None, dest=None) -> dict`** — genera un informe Markdown con:
   servidor/versión/computes, proyectos, topología del proyecto elegido (o el único abierto),
   hallazgos de `doctor` (o el equivalente del núcleo), y un apartado «pendiente de verificar»
   con lo que **no** se ha comprobado. Nada inventado: si un dato no se pudo leer, se escribe
   el error literal. Escribe en `~/GNS3/informes/informe-<fecha>.md` (o `dest`) y devuelve
   `{"path", "bytes", "content"}`.
   **No incluye credenciales** del config de GNS3 ni rutas de otros usuarios.

## Prohibido

No edites `gns3core.py`, `cli/gns3lab`, `tests/`, `docs/`, `README.md` ni `PROJECT.md`.
No `git push`, no PR, no cambio de rama. No ejecutes operaciones destructivas contra el servidor
real; las pruebas de `batch` son de solo lectura.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-batchmcp
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile gns3_mcp_server.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python - <<'EOF'
import asyncio, sys
sys.path.insert(0, ".")
import gns3_mcp_server as s
print("tools:", len(asyncio.run(s.mcp.list_tools())))
r = s.gns3_batch([
    {"tool": "gns3_status", "args": {}},
    {"tool": "gns3_topology", "args": {"project_name": "examen-kit"}},
])
print("batch:", r["ok"], len(r["results"]), r["total_ms"])
print("bloqueada:", s.gns3_batch([{"tool": "gns3_server", "args": {"action": "shutdown"}}]))
i = s.gns3_informe(project_name="examen-kit")
print("informe:", i["path"], i["bytes"])
EOF
```

Commit: `feat(mcp): batch de herramientas e informe con evidencia`. Informa de salida real.
