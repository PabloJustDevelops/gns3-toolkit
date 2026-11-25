# BRIEF — carril `pfmcp` (tools pfSense y velocidad del MCP)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-pfmcp` · rama `opencode/pfmcp`.

## Contexto

Dos objetivos en el mismo fichero `gns3_mcp_server.py` (nadie más lo toca):

1. Exponer pfSense nativo como tool, delegando en el módulo `pfsense.py` que otro carril crea.
2. Optimizar la velocidad: hoy `gns3_batch` ejecuta 5 operaciones de solo lectura en **52 ms**
   secuenciales (medido). Paralelizarlas debe bajar ese número. El arranque del MCP tarda
   ~3 s y `list_tools()` 8 ms.

Lee `AGENTS.md`, `PROJECT.md`, `gns3_mcp_server.py`, `gns3core.py` y
`orchestration/BRIEF-pfcore.md` (contrato de `pfsense.py`).

## Contrato pfSense

Tool `gns3_pfsense(action="status|config|assign|ip|dhcp|rule|nat|ssh|detect",
project_id=None, project_name=None, node=None, **kwargs)`:
- `detect` no necesita SSH: localiza el nodo pfSense del proyecto y devuelve
  `pfsense.detect_ifnames(node)` con el `adapter_type` real del nodo.
- Las demás acciones construyen `PfSense.from_env()` y delegan en el método correspondiente;
  devuelven `{ok, data, error}` sin filtrar credenciales.
- `assign` con `mapping` y `ip`/`dhcp`/`rule`/`nat` con sus parámetros del contrato de pfcore.
- Si faltan variables de entorno, devuelve un error que diga exactamente qué variable falta,
  **sin pedir el valor**.

## Contrato de velocidad

- En `gns3_batch`, ejecutar en paralelo con `concurrent.futures.ThreadPoolExecutor` las
  operaciones marcadas como de solo lectura (tools que empiezan por `gns3_status`, `gns3_projects`,
  `gns3_topology`, `gns3_templates`, `gns3_symbols`, `gns3_appliances`, `gns3_statistics`,
  `gns3_compute` con `action` de lectura, `gns3_pfsense` con `action` en `status|config|detect`).
  Las operaciones con efecto secundario siguen en orden secuencial.
- Preservar el orden de `results` por índice aunque se ejecuten en paralelo.
- Añadir a la respuesta `{"parallel": bool, "wall_ms": int}` junto a `total_ms` existente.
- Opcional: cache TTL de 2 s para consultas idénticas dentro de un mismo batch (mismo tool +
  mismos args). Si se añade, que sea explícito en la respuesta (`cache_hits`).

## Prohibido

No edites `gns3core.py`, `pfsense.py`, `cli/gns3lab`, `tests/`, `docs/`, `README.md` ni
`PROJECT.md`. No `git push`, no PR, no cambio de rama. No ejecutes acciones pfSense contra un
host real; las medidas de velocidad usan herramientas de solo lectura contra el servidor local.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-pfmcp
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile gns3_mcp_server.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python - <<'EOF'
import asyncio, sys, time
sys.path.insert(0, ".")
import gns3_mcp_server as s
print("tools:", len(asyncio.run(s.mcp.list_tools())))
t=time.perf_counter()
r=s.gns3_batch([{"tool":"gns3_status","args":{}} for _ in range(5)])
print("batch5:", r.get("total_ms"), "wall", round((time.perf_counter()-t)*1000),
      "parallel", r.get("parallel"), "cache_hits", r.get("cache_hits"))
print("ok:", r.get("ok"), "resultados:", len(r.get("results",[])))
EOF
```

Commit: `feat(mcp): tool gns3_pfsense y batch paralelo`. Informa de la salida real y de la
mejora medida (52 ms de referencia).
