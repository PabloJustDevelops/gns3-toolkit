# PROJECT.md — estado y rumbo

## Qué es

`gns3-toolkit` empaqueta la operación de un servidor GNS3 2.2 sin GUI: una librería
(`gns3core`), un servidor MCP de 18 tools y una CLI de 22 comandos. El objetivo inmediato
es el examen del 1 de diciembre de 2026: montar un escenario (pfSense + VLANs + NAT +
clientes) desde la terminal, con el VNC sólo como último recurso.

## Estado (2026-11-25, GUI portada + REA)

- `gns3core.py`: **12 áreas** de la API v2 (`API_V2_MAP`): las 11 de la GUI operativa más
  `nio_ports` (NIO y captura por puerto, acciones masivas, `resume`/`pause`, qemu img, VMs
  invitadas, `/v1/version` y el WebSocket de notificaciones). Inventario real de 78 rutas en
  `orchestration/inventario-rutas-gns3.txt`. Cuarta tanda (NIO en CLI/MCP/tests/docs) cerrada.
- CLI: **42 comandos**; MCP: **39 tools** (`hermes mcp test gns3` → Connected, 39 discovered).
- **Tests: 456 passed, cobertura 100 % de `gns3core.py`** (718 sentencias, 0 miss).
- Kit `examen-kit` arrancado (5/5 nodos) y `doctor` → **sin hallazgos**. Importado al servidor
  del aula como proyecto nuevo `Pablo Rodriguez Garijo - Kit` sin tocar el original.
- Documentación nueva: `docs/GUI-PORTADA.md` (50 filas), `API-COVERAGE.md` (97 filas),
  `COMPATIBILIDAD.md`, `PARIDAD.md` y el informe de REA
  `docs/research/ubridge-console-enganche.md` (23 KB). 0 enlaces rotos.

## Hitos

| # | Hito | Estado |
|---|---|---|
| 1 | Núcleo + MCP + CLI funcionando | hecho |
| 2 | Kit de examen verificado | hecho |
| 3 | Suite de tests sin servidor (307, cobertura 100 %) | hecho (`opencode/tests`, `gk2-tests`) |
| 4 | Gestión de plantillas por CLI (`template`) | hecho (`opencode/template`) |
| 5 | Paridad MCP/CLI (26 tools / 30 comandos) | hecho (`opencode/mcp`, `opencode/cli`) |
| 6 | Documentación completa | hecho (`opencode/docs`, `opencode/covdocs`) |
| 7 | Cobertura total de la API v2 operativa (8/8 áreas) | hecho (`bc75bc0` + carriles `gk2-*`) |
| 8 | GUI operativa portada (11 áreas, 78 rutas inventariadas) | hecho (`a5993aa` + carriles `gk3-*`) |
| 9 | NIO/captura por puerto, acciones masivas y eventos WS (12 áreas) | hecho (`7622e25` + carriles `gk4-*`) |
| 10 | REA de `ubridge` y vías de enganche documentadas | hecho (`opencode/rea`) |
| 11 | Publicar el repo (privado) | propuesto |

## Bitácora de los carriles paralelos (2026-11-25)

Cuatro worktrees desde `3320b4f`, agentes opencode en tabs de Herdr con modelos gratuitos
(`opencode-go/hungerg-free` y `opencode-go/hy4-flash-free`, fijados por `opencode.json` de
cada worktree, excluido de git). Reparto por ficheros para que no se pisaran: `tests/`,
`cli/gns3lab`, `gns3_mcp_server.py`, `docs/`+README. Briefs en `orchestration/`.

- `opencode/tests` → 53 tests + 1 xfail que documentaba un bug real de `Console.run`
  (respondía en bucle a `[y/n]` y se comía el timeout).
- `opencode/mcp` → `gns3_template`, `gns3_link_edit` y `gns3_console` delegando en
  `gns3_exec`; `_telnet` eliminado.
- `opencode/template` → `gns3lab template list|create|delete` y `doctor --json`.
- `opencode/docs` → 1059 líneas de documentación, 0 enlaces rotos.

El bug del xfail se arregló después del merge, en `master`, con el test en verde (54 passed).

### Pasada de cobertura total (2026-11-25, segunda tanda)

Cuatro worktrees nuevos desde `bc75bc0`, agentes `gk2-*` en tabs de Herdr con
`hy4-flash-free` (CLI, docs) y `hungerg-free` (MCP, tests). El cambio de modelo se hizo
por el selector `/models` de la TUI: el `opencode.json` por worktree **no** se aplicó en esta
oleada, a diferencia de la anterior. Dos agentes se bloquearon preguntando por «otro agente»
en su worktree; la comprobación de `/proc` mostró una sola instancia por directorio y se les
dijo que continuaran con su propio trabajo.

- `opencode/cli` → 30 comandos; añade `compute`, `stats`, `symbols`, `appliances`, `capture`,
  `console` y verbos nuevos en `node`, `link`, `draw`, `snap` y `template`.
- `opencode/mcp` → 26 tools; añade `gns3_compute`, `gns3_statistics`, `gns3_symbols`,
  `gns3_appliances`, `gns3_node_action`, `gns3_command_line` y `update` en links/drawings.
- `opencode/tests` → **307 tests, 100 % de cobertura** de `gns3core.py` (576 sentencias).
- `opencode/covdocs` → `API-COVERAGE.md`, `COMPATIBILIDAD.md` y `PARIDAD.md`.

Gates repetidos en `master` tras los cuatro merges: 307 passed con `--cov-fail-under=100`,
26 tools conectadas por `hermes mcp test`, 30 comandos en la CLI y `doctor` sin hallazgos.
No hubo que arreglar ningún bug nuevo: los cuatro carriles llegaron limpios.

**Compatibilidad 3.x no declarada**: usa `/v3` con token y no hay servidor 3.x donde
verificarla. El detalle está en `docs/COMPATIBILIDAD.md`.

### Tercera tanda: GUI operativa + REA (2026-11-25)

El inventario de 78 rutas se extrajo del código de `gns3server` 2.2.61, que es Python
legible en `~/Applications/gns3/venv/lib/python3.14/site-packages/gns3server/handlers`.
El núcleo se amplió en ~40 métodos antes de repartir trabajo, para que CLI y MCP
programaran contra un contrato único.

Cinco worktrees desde `a5993aa`, agentes `gk3-*` en Herdr con `hy4-flash-free`
(CLI, docs) y `hungerg-free` (MCP, tests, REA). Modelos fijados con `/models` en la TUI.
Ningún agente pidió decisiones bloqueantes y los cinco mergearon sin conflictos.

- `opencode/guicli` → 36 comandos; GUI a CLI (computes, gns3vm, símbolos, notificaciones,
  emuladores, project file/stats, resize_disk, idle-pc…).
- `opencode/guimcp` → 34 tools con la misma superficie; acciones destructivas con `confirm`.
- `opencode/guitests` → 416 tests, 100 % de cobertura (677 sentencias).
- `opencode/guidocs` → `GUI-PORTADA.md`, matriz de 78 rutas y compatibilidad honesta.
- `opencode/rea` → `docs/research/ubridge-console-enganche.md`: ubridge 1.3.2 no stripped
  (SHA-256 `b72944a4…f326c`), UDP/UNIX como NIO, TCP/UNIX como hipervisor de control,
  pcap para capturas, y **sin evidencia estática de Telnet/VNC/WebSocket**: la consola la
  sirve `gns3server`, no ubridge. Por eso la recomendación del informe es API primero.

Gates repetidos en `master`: 416 passed con `--cov-fail-under=100`, 34 tools conectadas,
36 comandos y `doctor` sin hallazgos. Al reiniciar el servidor hubo que levantar
`gns3-server` y `libvirtd` de nuevo; están activos y los cinco nodos del kit arrancados.

### Cuarta tanda: NIO, capturas por puerto y evento WS (2026-11-25)

Cuatro worktrees desde `fbac815`, agentes `gk4-*` con `hy4-flash-free` (CLI, docs) y
`hungerg-free` (MCP, tests). El núcleo se amplió antes con `port_nio`, `port_capture`,
`nodes_action`, `nodes_console_reset`, `resume|pause|unpause`, qemu img, VMs y WS.

- `opencode/niocli` → 42 comandos; `nio`, `capture-port`, `all`, `disk`, `vm`, `watch`,
  `version-v1` y acciones masivas con confirmación.
- `opencode/niomcp` → 39 tools; `gns3_nio`, `gns3_port_capture`, `gns3_nodes_bulk`,
  `gns3_events`, `gns3_events_url`, `gns3_nodes_bulk` con `confirm=True`.
- `opencode/niotests` → 456 tests, 100 % de cobertura (718 sentencias).
- `opencode/niodocs` → `NIO-Y-CAPTURAS.md`, `EVENTOS.md`, `LIMITES-CONTROLLER-COMPUTE.md`
  y README corregido (los números se recuentan desde el código, no se copian).

Gates en `master`: 456 passed con `--cov-fail-under=100`, 39 tools conectadas, 42 comandos y
`doctor` sin hallazgos. El mismo día se importó el kit al servidor del aula (`192.168.71.251`)
como proyecto nuevo, sin modificar `Pablo Rodriguez Garijo` (`db277172…5cf`).


## Límites conocidos

- Sólo GNS3 2.2.x (API `/v2`). La 3.x no está soportada.
- `gns3_upload` y `clone_disk` operan sobre el compute **local**; en un servidor remoto del aula
  el disco tiene que estar ya allí o subirse con `gns3lab port`.
- `console` (puerto VNC) no se puede fijar por `PUT` en un nodo; se fija en la plantilla.
- El OCR lee 720x400 (fuente VGA 9x16); no espera leer texto pequeño.

## Decisiones

- **Estructura plana** (`gns3core.py` y `gns3_mcp_server.py` en la raíz): el MCP hace
  `import gns3core` y la CLI añade la raíz a `sys.path`. Un paquete `src/` no aporta nada aquí y
  añadiría una capa de rotura justo antes del examen.
- **Un solo núcleo** compartido por MCP y CLI, para que una corrección llegue a los dos.
- **Sin dependencias en el núcleo**: `fastmcp`/`httpx` sólo en el servidor MCP; `pillow` es
  opcional con caída a ImageMagick y luego a PPM.
