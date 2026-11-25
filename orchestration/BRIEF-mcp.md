# BRIEF — carril `mcp`

Eres un agente de coding. Trabajas SOLO en este worktree:

- Ruta: `/home/pablorg/Proyectos/gns3-toolkit-wt-mcp`
- Rama: `opencode/mcp` (ya creada, no cambies de rama)

## Contexto que no se infiere del código

`gns3_mcp_server.py` es un servidor MCP (fastmcp) de 18 tools sobre un GNS3 2.2. Importa
`gns3core`, que es el núcleo compartido. Hay un servidor real en `http://127.0.0.1:3080`
(proyectos `Practica VPN` y `examen-kit`); úsalo para verificar, sin crear ni borrar proyectos.

Lee antes de escribir: `AGENTS.md`, `PROJECT.md`, `gns3_mcp_server.py` (completo),
`gns3core.py` (para saber qué hay), y `cli/gns3lab` **solo** para copiar contratos de nombres.

## Qué tienes que entregar

1. **Tool `gns3_template`** con `action: list|create|delete|apply` y **exactamente estos
   parámetros** (otro carril construye la CLI con el mismo contrato):
   - `list` → nombres, tipo y `template_id` de las plantillas.
   - `create` → `from_node` (nombre o id) **o** `node_type` + `properties`; `name`, `console`
     opcional. `POST /v2/templates` con `compute_id: "local"`. Con `console` lo fija a nivel de
     plantilla y lo verifica releyendo (el `PUT` sobre un nodo lo ignora).
   - `delete` → por nombre o id, devuelve `{deleted: bool}`.
   - `apply` → instancia la plantilla en un proyecto (`x`, `y`, `name`), que es lo que ya hace
     `gns3_node_edit(action=create, template=...)`: si vas a duplicar esa ruta, haz que `apply`
     delegue en ella en vez de repetir código.
2. **Tool `gns3_link_edit`** con `action: add|delete|list`, `node_a`/`node_b`,
   `adapter_a`/`adapter_b` (por defecto 0) y `port_a`/`port_b` (por defecto 0).
   Valida antes de enviar: si el nodo es `ethernet_switch`, el puerto es `port_*` y el adapter
   es 0 (un switch tiene 8 puertos en el adapter 0) — un `adapter` mal puesto devuelve
   `404 Port X/0 for SW1 not found`, y la tool debe explicarlo en vez de propagar el 404.
3. **Retirar la consola vieja.** `gns3_console` usa hoy un `_telnet` con `settle` fijo (espera
   ciega) mientras `gns3_exec` usa `core.Console` (por prompt/quietud). Migra `gns3_console`
   para que **delegue en `gns3_exec`** conservando su firma pública y su forma de respuesta, o
   márcala como alias. El objetivo: que no quede ningún camino de consola con `sleep` fijo.
   Elimina `_telnet` si queda sin usuarios, y dilo.

## Reglas de la casa

- Las tools devuelven datos; no imprimen.
- Los errores se devuelven como `{"error": "..."}` con el mensaje interno, no con el volcado
  de schema.
- Toda tool nueva va antes de `if __name__ == "__main__": mcp.run()`.
- Tras añadir tools, el fichero debe importar limpio con
  `env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python`.

## Prohibido

- **No edites** `gns3core.py`, `cli/gns3lab` ni `tests/`.
- No toques `README.md`, `docs/`, `PROJECT.md` (carril `docs`).
- No `git push`, no PR. No cambies de rama. No crees ni borres proyectos reales.

## Gates (pega la salida real)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-mcp
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile gns3_mcp_server.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python - <<'EOF'
import asyncio, sys
sys.path.insert(0, ".")
import gns3_mcp_server as s
tools = asyncio.run(s.mcp.list_tools())
print(len(tools), [t.name for t in tools])
print(s.gns3_template(action="list")[:2])
EOF
```

Deben salir **20 tools** (18 + `gns3_template` + `gns3_link_edit`).

## Entrega

Commit en tu rama, mensaje `feat(mcp): tools template y link_edit, consola unificada`, y en el
informe: salida literal de los gates, forma exacta de la respuesta de `gns3_template(list)` y
qué pasó con `_telnet`.
