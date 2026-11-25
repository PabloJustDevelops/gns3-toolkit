# Velocidad del MCP: `gns3_batch`

Secciones: Lo que hace en esta rama · Qué se paraleliza · Cómo medirlo.

Hoy una sesión con el agente paga el arranque del servidor MCP y una llamada por cada lectura.
`gns3_batch` agrupa varias lecturas en **una** llamada y devuelve evidencia con tiempos; la
superficie de tools se recuenta con `mcp.list_tools()`, nunca se copia de un documento.

## Lo que hace en esta rama

Definido en `gns3_mcp_server.py`, con estas reglas verificadas en el código:

- Acepta hasta 20 operaciones. Cada una es `{"tool": "gns3_status", "args": {...},
  "confirm": true}`; `project_name` se inyecta en la tool si la operación no fija proyecto y la
  tool lo admite.
- `results` es una lista con un `index` por operación: el orden de salida corresponde al orden
  de entrada, aunque una operación falle. Cada entrada lleva `tool`, `ok`, `ms` y, según el
  caso, `result` o `error`.
- Las tools destructivas (`gns3_server`, borrados de `gns3_projects` y `gns3_node_edit`,
  `stop`/`reload` de `gns3_node_action`, `gns3_project_io delete/import` y `gns3_nodes_bulk`)
  se bloquean salvo que la operación traiga `"confirm": true`. `gns3_batch` no se puede anidar.
- `stop_on_error=True` corta el lote en el primer fallo; si no, los errores quedan aislados.
- La respuesta global tiene `ok`, `total_ms` y `wall_ms` (medidos con `perf_counter`),
  `parallel` y `cache_hits`.
- **La ejecución paraleliza lecturas contiguas** con `ThreadPoolExecutor` y reutiliza consultas
  idénticas durante 2 s dentro del lote (`cache_hits`). Las operaciones con efecto secundario
  siguen en orden secuencial, y un cambio de modo vacía la caché.

Ejemplo:

```python
r = gns3_batch([
    {"tool": "gns3_status", "args": {}},
    {"tool": "gns3_projects", "args": {"action": "list"}},
])
print(r["ok"], r["total_ms"], [(x["index"], x["tool"], x["ok"]) for x in r["results"]])
```

## Qué se paraleliza

`_batch_is_read_only()` clasifica como lectura, y por tanto paralelizable:

- `gns3_status`, `gns3_topology`, `gns3_templates`, `gns3_appliances`, `gns3_statistics`;
- `gns3_projects` en `list`/`info`;
- `gns3_symbols` en `list`/`dimensions`/`raw`/`default`;
- `gns3_compute` en `info`/`list`/`ports` y `call` sin body;
- `gns3_pfsense` en `status`/`config`/`detect`.

Las lecturas contiguas se lanzan en un `ThreadPoolExecutor` y `results` conserva el orden por
`index`. Cualquier operación con efecto secundario (o `stop_on_error=True`) vuelve al modo
secuencial. La tool `gns3_pfsense` expone `status|config|assign|ip|dhcp|rule|nat|ssh|detect`;
`detect` no necesita SSH y usa `pfsense.detect_ifnames(node)`. Ver
[PFSENSE-NATIVO.md](PFSENSE-NATIVO.md).

No hay cifra de mejora prometida: mide en tu máquina.

## Cómo medirlo

Ejecutado desde la raíz del repo:

```bash
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile gns3_mcp_server.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python - <<'EOF'
import asyncio, sys, time
sys.path.insert(0, ".")
import gns3_mcp_server as s
print("tools:", len(asyncio.run(s.mcp.list_tools())))
t=time.perf_counter()
r=s.gns3_batch([{"tool":"gns3_events_url","args":{}} for _ in range(5)])
print("batch5:", r.get("total_ms"), "wall", round((time.perf_counter()-t)*1000),
      "parallel", r.get("parallel"), "cache_hits", r.get("cache_hits"))
print("ok:", r.get("ok"), "resultados:", len(r.get("results",[])))
EOF
```

`gns3_events_url` compone la URL y no necesita servidor, así que esta medición comprueba la
forma de la respuesta sin depender del GNS3. Salida real de este árbol:

```text
tools: 42
batch5: 1 wall 1 parallel False cache_hits 0
ok: True resultados: 5
```

`parallel=False` porque las cinco operaciones son idénticas y la caché las resuelve antes de
paralelizar; `cache_hits` cuenta las reutilizadas. Con lecturas distintas, el lote las agrupa en
paralelo. Los tiempos dependen del servidor y de la carga: compara siempre `total_ms`, `wall_ms`
y `cache_hits` en la misma máquina.

Contexto de la arquitectura en [ARQUITECTURA.md](ARQUITECTURA.md) y superficie completa en
[API-COVERAGE.md](API-COVERAGE.md).
