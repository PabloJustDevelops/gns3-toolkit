# PROJECT.md — estado y rumbo

## Qué es

`gns3-toolkit` empaqueta la operación de un servidor GNS3 2.2 sin GUI: una librería
(`gns3core`), un servidor MCP de 18 tools y una CLI de 22 comandos. El objetivo inmediato
es el examen del 1 de diciembre de 2026: montar un escenario (pfSense + VLANs + NAT +
clientes) desde la terminal, con el VNC sólo como último recurso.

## Estado (2026-11-25)

- `gns3core.py`: `Client`, `Console` (prompt/quietud, `--More--`, `[y/n]`, `Password:`),
  `QemuMonitor` (sendkey, type_text con wake, screendump PNG, OCR), utilidades de fichero de nodo.
- MCP: 18 tools, verificadas con `hermes mcp test gns3`.
- CLI: 22 comandos, verificados contra GNS3 2.2.61 local (VPCS, switch, NAT, pfSense).
- Kit `examen-kit` montado y probado end-to-end: PF1 (disco clonado, arranca al menú),
  NAT1 en WAN, SW1, PC1/PC2 con DHCP 192.168.1.100/101, `ping 8.8.8.8` con 0 % pérdida.
- Tests: pendiente (carril abierto).

## Hitos

| # | Hito | Estado |
|---|---|---|
| 1 | Núcleo + MCP + CLI funcionando | hecho |
| 2 | Kit de examen verificado | hecho |
| 3 | Suite de tests sin servidor | en curso |
| 4 | Gestión de plantillas por CLI (`template`) | en curso |
| 5 | Paridad MCP/CLI completa | en curso |
| 6 | Publicar el repo (privado) y README de uso | propuesto |

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
