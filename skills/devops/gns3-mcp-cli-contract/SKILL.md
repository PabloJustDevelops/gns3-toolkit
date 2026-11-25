---
name: gns3-mcp-cli-contract
description: Contrato de --json, gns3_batch, recursos y tools MCP.
version: 0.1.0
author: Pablo Rodríguez Garijo (PabloJustDevelops), Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [gns3, mcp, cli, json, batch]
    related_skills: [gns3-toolkit-operator, gns3-pfsense-native]
---

# Contrato CLI y MCP

Dos superficies sobre el mismo núcleo: `gns3lab` para shell y tools `gns3_*` para agentes.
Este contrato fija la forma de los datos, el lote de lecturas y qué tool usar sin ambigüedad.
No repitas por shell una llamada MCP que ya hiciste en la misma operación.

## When to Use

- Necesitas parsear la salida de `gns3lab` o encadenar sus códigos de salida.
- Vas a agrupar lecturas del MCP o dudas entre `gns3_exec`, `gns3_monitor` y `gns3_console`.
- Necesitas leer un resource o lanzar un prompt del MCP.
- No usar para configurar pfSense: eso es `gns3-pfsense-native`. Para elegir la vía por
  primera vez: `gns3-toolkit-operator`.

## Contrato `--json`

- `--json` vale como opción global, antes del subcomando: `gns3lab --json status`.
- Si el handler ya emite JSON, se respeta; si no, se envuelve como
  `{"cmd", "ok", "output"}`. `stderr` no se captura y el código de salida se conserva.
- Códigos: `0` correcto; `1` fallo de nodo, enlace o comprobación; `2` servidor sin respuesta.
- Los subcomandos `pf` devuelven `{ok, data}`; `pf detect` no usa SSH ni credenciales.
- Consume campos (`ok`, `output`, `data`, `error`), no el texto decorado ni el schema anidado
  de la API.

```bash
gns3lab --json status examen-kit
gns3lab --json doctor examen-kit
```

## Contrato `gns3_batch`

- Acepta hasta 20 operaciones con forma `{"tool": "...", "args": {...}}`; no se anida.
- `project_name` se inyecta en la operación si ésta no fija proyecto y la tool lo admite.
- `results` conserva el orden de entrada; cada entrada lleva `index`, `tool`, `ok`, `ms` y
  `result` o `error`.
- Las lecturas contiguas se paralelizan; las consultas idénticas se reutilizan durante 2 s
  (`cache_hits`). Los efectos secundarios van en orden secuencial.
- Las tools destructivas exigen `"confirm": true` dentro de la operación; sin eso se bloquean
  antes de llamar.
- La respuesta global lleva `ok`, `total_ms`, `wall_ms`, `parallel` y `cache_hits`.
- `stop_on_error=True` corta en el primer fallo y desactiva el paralelismo.
- Úsalo para diagnosticar con varias lecturas, no para escribir pasos que dependan del anterior.

```python
r = gns3_batch([
    {"tool": "gns3_status", "args": {}},
    {"tool": "gns3_projects", "args": {"action": "list"}},
])
print(r["ok"], [(x["index"], x["tool"], x["ok"]) for x in r["results"]])
```

## Resources y prompts

| Recurso | Devuelve | Efecto |
|---|---|---|
| `gns3://status` | versión, computes y proyecto abierto | ninguno |
| `gns3://projects` | id, nombre y estado | ninguno |
| `gns3://templates` | plantillas con id, tipo y nombre | ninguno |
| `gns3://project/{project}/topology` | nodos y enlaces | no abre el proyecto |

- `gns3-diagnostico(proyecto)`: guion de diagnóstico sin VNC y con evidencia real.
- `gns3-examen(servidor="clase")`: guion para montar, verificar y portar el lab del examen.
- Los resources son de lectura. No los uses para cambiar estado ni para escribir ficheros.

## Elige la tool

| Quiero | Tool |
|---|---|
| Estado del servidor | `gns3_status` |
| Proyectos: listar, abrir, crear, borrar | `gns3_projects(action=...)` |
| Nodos y enlaces de la topología | `gns3_topology` |
| Listar o editar nodos y enlaces | `gns3_nodes`, `gns3_links` |
| Consola de texto de un nodo | `gns3_exec` (`gns3_console` es alias) |
| Pantalla o menú de un nodo QEMU | `gns3_monitor(action="text"|"key"|"type")` |
| pfSense nativo | `gns3_pfsense(action=...)` |
| Arrancar, parar o reiniciar un nodo | `gns3_node_action` |
| Acción masiva sobre todos los nodos | `gns3_nodes_bulk(confirm=True)` |
| Informe del laboratorio | `gns3_informe` |
| Varias lecturas en una llamada | `gns3_batch` |

Si una tool devuelve `error`, no la reintentes con otro nombre: lee `valid` o pide el
`project_id`. No inventes tools ni cifras; recuéntalas con `mcp.list_tools()`.

## Procedimiento

1. Fija la superficie: shell y scripts por `gns3lab`; agente con MCP por tools `gns3_*`.
   Criterio: una sola vía por operación, sin duplicar la misma lectura.
2. Para CLI, añade `--json` y comprueba el exit code. Criterio: el JSON tiene `ok` y el código
   es `0`; si es `2`, el servidor no responde.
3. Para lecturas MCP, usa un resource si existe; si son varias, `gns3_batch`. Criterio: cada
   resultado trae `index` y `ok`, y los fallos quedan aislados.
4. Para acciones, llama a la tool específica. Si es destructiva o masiva, exige `confirm`.
   Criterio: el resultado relee el estado real, no sólo el `200` del POST.
5. Cierra con evidencia: `gns3_informe` o `gns3lab doctor`. Criterio: hallazgos y salida real
   pegados en el informe.

## Pitfalls

- `gns3_console` delega en `gns3_exec`; no llames a las dos para el mismo comando.
- `gns3_nodes(action="start")` acepta patrones y puede tocar varios nodos; para uno solo usa
  `gns3_node_action`.
- En `gns3_batch`, una escritura sin `confirm` se bloquea; no se ejecuta parcialmente.
- `gns3_batch` no admite más de 20 operaciones ni otro `gns3_batch` dentro.
- `gns3://project/{project}/topology` no abre el proyecto: si está cerrado, no cambia su estado.
- Un `200 OK` de la API no prueba configuración ni conectividad; exige ping, regla o pantalla.
- No fijes el número de tools de memoria: cambia por oleadas y el código es la fuente.

## Verification

```bash
gns3lab --json status
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python - <<'PY'
import gns3_mcp_server as s
r = s.gns3_batch([{"tool": "gns3_events_url", "args": {}}])
print(r["ok"], len(r["results"]), r["results"][0]["ok"])
PY
```

Criterio: el primer comando imprime JSON válido con `ok`; el lote imprime `True 1 True`.
`gns3_events_url` no necesita servidor, así que el humo prueba la forma de la respuesta.
