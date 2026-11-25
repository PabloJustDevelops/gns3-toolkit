# Velocidad del MCP: `gns3_batch`

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
- La respuesta global tiene `ok` y `total_ms` (milisegundos medidos con `perf_counter`).
- **La ejecución es secuencial en esta rama**: no hay campos `parallel`, `wall_ms` ni
  `cache_hits`. Eso es lo previsto en el carril `pfmcp`, descrito abajo.

Ejemplo:

```python
r = gns3_batch([
    {"tool": "gns3_status", "args": {}},
    {"tool": "gns3_projects", "args": {"action": "list"}},
])
print(r["ok"], r["total_ms"], [(x["index"], x["tool"], x["ok"]) for x in r["results"]])
```

## Lo previsto en el carril `pfmcp`

Según `orchestration/BRIEF-pfmcp.md` (aún no aplicado aquí):

- Las operaciones de solo lectura — `gns3_status`, `gns3_projects`, `gns3_topology`,
  `gns3_templates`, `gns3_symbols`, `gns3_appliances`, `gns3_statistics`, `gns3_compute` en
  acción de lectura y `gns3_pfsense` en `status|config|detect` — se ejecutan en paralelo con
  `concurrent.futures.ThreadPoolExecutor`. Las que tienen efecto secundario siguen en orden
  secuencial.
- `results` mantiene el orden por `index` aunque se ejecuten en paralelo.
- La respuesta añade `parallel` y `wall_ms` junto a `total_ms` existente.
- Caché opcional con TTL de 2 s para operaciones idénticas dentro del mismo lote; si se
  activa, se declara con `cache_hits`.
- La tool `gns3_pfsense` expone `status|config|assign|ip|dhcp|rule|nat|ssh|detect`; `detect`
  no necesita SSH y usa `pfsense.detect_ifnames(node)`. Ver
  [PFSENSE-NATIVO.md](PFSENSE-NATIVO.md).

No hay cifra de mejora prometida: mide en tu máquina.

## Cómo medirlo

El comando del gate del carril `pfmcp`, ejecutado desde la raíz del repo:

```bash
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

Salida real de esta rama (batch secuencial, servidor local, sin paralelismo ni caché):

```text
tools: 41
batch5: 84 wall 84 parallel None cache_hits None
ok: True resultados: 5
```

El carril `pfmcp` toma como referencia **52 ms** para 5 lecturas secuenciales medidas en su
entorno; la cifra viene de su brief, no de una promesa de este documento. Los tiempos dependen
del servidor y de la carga: compara siempre `total_ms`, `wall_ms` y `cache_hits` en la misma
máquina antes y después del cambio.

Contexto de la arquitectura en [ARQUITECTURA.md](ARQUITECTURA.md) y superficie completa en
[API-COVERAGE.md](API-COVERAGE.md). El contrato del carril está en el brief `pfmcp` del
workspace de orquestación (`orchestration/BRIEF-pfmcp.md`), que no forma parte de este repo.
