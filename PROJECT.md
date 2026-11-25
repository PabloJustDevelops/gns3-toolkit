# PROJECT.md — estado y rumbo

## Qué es

`gns3-toolkit` empaqueta la operación de un servidor GNS3 2.2 sin GUI: una librería
(`gns3core`), un servidor MCP de 18 tools y una CLI de 22 comandos. El objetivo inmediato
es el examen del 1 de diciembre de 2026: montar un escenario (pfSense + VLANs + NAT +
clientes) desde la terminal, con el VNC sólo como último recurso.

## Estado (2026-11-25, pasada de cobertura total)

- `gns3core.py`: superficie v2 completa (computes, statistics, symbols, appliances, imágenes,
  proyectos, plantillas, nodos, enlaces, capturas, dibujos, snapshots, consola y monitor).
  `API_V2_MAP` declara las 8 áreas cubiertas.
- MCP: **26 tools**, verificadas con `hermes mcp test gns3` (Connected, 26 discovered).
- CLI: **30 comandos**, verificados contra GNS3 2.2.61 local.
- **Tests: 307 passed, cobertura 100 % de `gns3core.py`** (576 sentencias, 0 miss;
  `--cov-fail-under=100`), sin servidor GNS3.
- Kit `examen-kit` arrancado y `gns3lab doctor` → **sin hallazgos**.
- Documentación: `COMANDOS`, `EXAMEN`, `ARQUITECTURA`, `TROUBLESHOOTING`, `API-COVERAGE`,
  `COMPATIBILIDAD` y `PARIDAD` (matrices de 47 y 70 filas, 0 enlaces rotos).

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
| 8 | Publicar el repo (privado) | propuesto |

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
