# PROJECT.md — estado y rumbo

## Qué es

`gns3-toolkit` empaqueta la operación de un servidor GNS3 2.2 sin GUI: una librería
(`gns3core`), un servidor MCP de 18 tools y una CLI de 22 comandos. El objetivo inmediato
es el examen del 1 de diciembre de 2026: montar un escenario (pfSense + VLANs + NAT +
clientes) desde la terminal, con el VNC sólo como último recurso.

## Estado (2026-11-25)

- `gns3core.py`: `Client`, `Console` (prompt/quietud, `--More--`, `[y/n]`, `Password:`),
  `QemuMonitor` (sendkey, type_text con wake, screendump PNG, OCR), utilidades de fichero de nodo.
- MCP: **20 tools**, verificadas con `hermes mcp test gns3` (`Connected`, 20 discovered).
- CLI: **23 comandos** (22 + `template`), verificados contra GNS3 2.2.61 local.
- **Tests: 54 passed** (`pytest -q`), sin servidor: dobles de HTTP, telnet y HMP.
- Kit `examen-kit` montado y probado end-to-end: PF1 (disco clonado, arranca al menú),
  NAT1 en WAN, SW1, PC1/PC2 con DHCP `192.168.1.100/101`, `ping 8.8.8.8` con 0 % pérdida.
- Docs: `docs/COMANDOS.md` (23 secciones), `EXAMEN.md`, `ARQUITECTURA.md`,
  `TROUBLESHOOTING.md` y README reescrito.

## Hitos

| # | Hito | Estado |
|---|---|---|
| 1 | Núcleo + MCP + CLI funcionando | hecho |
| 2 | Kit de examen verificado | hecho |
| 3 | Suite de tests sin servidor (54) | hecho (`opencode/tests`) |
| 4 | Gestión de plantillas por CLI (`template`) | hecho (`opencode/template`) |
| 5 | Paridad MCP/CLI (`template`, `link_edit`, consola única) | hecho (`opencode/mcp`) |
| 6 | Documentación completa | hecho (`opencode/docs`) |
| 7 | Publicar el repo (privado) | propuesto |

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
