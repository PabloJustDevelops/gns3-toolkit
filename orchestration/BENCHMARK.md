# Banco de rendimiento (`scripts/bench.py`)

Banco reproducible para medir velocidad y errores de las capas de `gns3-toolkit`
**sin servidor GNS3 real**: la API sale de `FakeApi` y el resto es CPU del propio
equipo. No arranca nodos, no escribe ficheros de estado y no toca la configuración
de `~/.config/GNS3`.

## Uso

```bash
.venv/bin/python scripts/bench.py --quick   # pocas repeticiones, para la suite
.venv/bin/python scripts/bench.py --full    # banco completo, para el informe
```

Código de salida: `0` si todas las medidas se completaron, `1` si alguna lanzó una
excepción o devolvió un resultado inesperado. La última línea siempre es
`exit_code=0` o `exit_code=1`.

Salida: una línea `metric <nombre> n=… median_ms=… p95_ms=… ok=1` por medida, más
`ratio …` cuando hay dos medidas comparables.

## Qué mide cada capa

| Métrica | Qué ejecuta | Repeticiones (`--quick` / `--full`) |
|---|---|---|
| `cli_help` | Proceso nuevo `.venv/bin/python cli/gns3lab --help`; incluye arranque del intérprete y carga de la CLI | 2 / 5 |
| `mcp_list_tools` | `asyncio.run(gns3_mcp_server.mcp.list_tools())` en proceso, tras un calentamiento | 3 / 10 |
| `mcp_tools` | Número de tools devueltas por `list_tools()` (no es una medida de tiempo) | — |
| `batch_parallel` | `gns3_batch` con 5 lecturas contiguas (thread pool) | 3 / 7 |
| `batch_sequential` | El mismo lote con `stop_on_error=True`, que fuerza el camino secuencial del mismo `gns3_batch` | 3 / 7 |
| `pfsense_parse` | `pfsense.parse_config()` de un `config.xml` representativo (interfaces, DHCP, 4 reglas, NAT, sección desconocida con atributos) | 3 / 10 |
| `pfsense_render` | `pfsense.render_config()` del documento parseado | 3 / 10 |
| `json_informe` | Tamaño del informe representativo serializado | — |
| `json_serialize` | `json.dumps(..., ensure_ascii=False, indent=2, sort_keys=True)` de ese informe (25 nodos, 24 enlaces) | 3 / 10 |

Cada lectura del lote hace un `GET` real contra `FakeApi` (de `tests/conftest.py`)
en `127.0.0.1` y después duerme **20 ms** (`LATENCIA_LOTE_S`). El retardo es
deliberado: el doble local responde en microsegundos y sin él no se puede medir el
solape del `ThreadPoolExecutor`. Es una latencia simulada, no una cifra del servidor.

`p95` se calcula como el percentil 95 por índice sobre las muestras ordenadas; con
`n=5` equivale prácticamente al máximo observado. Los ratios sólo se publican
cuando existen dos medidas comparables; **no hay una línea base histórica** de este
repo, así que no se inventan ratios «antes/después».

## Entorno de la ejecución registrada

- Fecha: 2026-11-26 (UTC+01:00)
- Python: 3.12.14 (`.venv`)
- fastmcp: 4.2.6
- SO: CachyOS, Linux 7.3.5-2-cachyos, x86_64, glibc 2.44
- CPU: Intel Core i5-10500H, 12 hilos lógicos
- Comando: `env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python scripts/bench.py --full`

## Números reales del `--full`

Ejecución del 2026-11-26 00:08:55 (salida literal):

| Métrica | n | mediana (ms) | p95 (ms) |
|---|---:|---:|---:|
| `cli_help` | 5 | 95,103 | 97,157 |
| `mcp_list_tools` | 10 | 0,551 | 0,753 |
| `batch_parallel` | 7 | 22,686 | 23,044 |
| `batch_sequential` | 7 | 109,486 | 113,788 |
| `pfsense_parse` | 10 | 0,061 | 0,109 |
| `pfsense_render` | 10 | 0,108 | 0,188 |
| `json_serialize` | 10 | 0,413 | 0,489 |

- `mcp_tools`: **42** tools.
- `batch_lecturas`: 5 lecturas, 20 ms simulados cada una.
- `json_informe`: 14 451 bytes.
- **Ratio**: `batch_sequential / batch_parallel` = 109,486 / 22,686 = **4,83x**.
- `exit_code=0`.

### Variabilidad observada

El banco es de un solo proceso y no fija la frecuencia de CPU. En una ejecución
`--full` anterior, con el equipo cargado, `pfsense_parse` dio 0,253 ms de mediana y
`json_serialize` 1,770 ms (frente a 0,061 y 0,413 en la tabla). Son las mismas
operaciones: la diferencia es ruido del entorno. Para comparar cambios, ejecutar
las dos versiones en la misma sesión y comparar medianas, no una ejecución aislada.
Una repetición posterior del `--full` dio 97,527 ms en `cli_help`, 22,828 ms en
paralelo, 103,566 ms en secuencial (ratio 4,54x) y 0,058/0,417 ms en pfSense/JSON:
el mismo orden de magnitud, con la diferencia esperable entre ejecuciones.

## Lo que este banco no mide

- Latencia del servidor GNS3 real (API, arranque de nodos, QEMU), consolas telnet,
  HMP, OCR y VNC: requieren el servidor y no forman parte de una suite sin estado.
- Memoria, CPU o coste energético: sólo se mide tiempo de pared.
- Ratios antes/después de commits anteriores: no existe una línea base guardada.
  El único ratio disponible es paralelo frente a secuencial dentro del lote.
