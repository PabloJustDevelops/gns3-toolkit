# BRIEF — carril `mcpres` (resources y prompts del MCP)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-mcpres` · rama `opencode/mcpres`.

## Contexto

El servidor MCP tiene 39 tools, pero **ningún resource ni prompt**: al lanzarlo, un agente solo
ve herramientas y tiene que pedir los datos. Hay que exponer los datos útiles como resources y
dos guiones como prompts. Lee `AGENTS.md`, `PROJECT.md`, `gns3_mcp_server.py`, `gns3core.py` y
la API de fastmcp instalada en `.venv` (comprueba las firmas reales de `mcp.resource` y
`mcp.prompt`, no las inventes).

## Contrato

Resources (URI exacto):

| URI | Contenido |
|---|---|
| `gns3://status` | versión, computes y estado del servidor |
| `gns3://projects` | lista de proyectos con id, nombre y estado |
| `gns3://project/{project}/topology` | nodos (nombre, tipo, estado, consola) y enlaces del proyecto |
| `gns3://templates` | plantillas con id, tipo y nombre |

Prompts (nombre exacto):

| Prompt | Argumentos | Contenido |
|---|---|---|
| `gns3-diagnostico` | `proyecto: str` | Guion para diagnosticar un lab: `doctor`, topología, consola por prompt, monitor/OCR, verificación con ping. |
| `gns3-examen` | `servidor: str = "clase"` | Guion del examen: arrancar, leer pantalla, asignar interfaces, VLANs, verificar y portar. Debe remitir a `~/GNS3/CHULETA.md` sin copiar secretos. |

Requisitos:
- Los resources devuelven datos legibles (JSON o texto), nunca `print`.
- Si el proyecto no existe o hay varios con ese nombre, el resource devuelve un mensaje de error
  claro con los nombres disponibles; no elige uno a ciegas.
- Los prompts no incluyen credenciales ni rutas de otro usuario.
- Todo antes de `if __name__ == "__main__": mcp.run()`.

## Prohibido

No edites `gns3core.py`, `cli/gns3lab`, `tests/`, `docs/`, `README.md` ni `PROJECT.md`.
No `git push`, no PR, no cambio de rama. No crees ni borres proyectos en el servidor del aula.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-mcpres
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile gns3_mcp_server.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python - <<'EOF'
import asyncio, sys
sys.path.insert(0, ".")
import gns3_mcp_server as s
r = asyncio.run(s.mcp.list_resources()); p = asyncio.run(s.mcp.list_prompts())
print("resources:", len(r), [str(getattr(x, "uri", x)) for x in r])
print("prompts:", len(p), [x.name for x in p])
EOF
```

Commit: `feat(mcp): resources y prompts para inspeccionar el lab sin llamadas extra`. Informa de
la salida real y de la firma exacta usada para registrar resources/prompts.
