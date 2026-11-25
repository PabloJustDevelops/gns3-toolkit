---
name: gns3-toolkit-operator
description: Elige CLI, MCP o núcleo y opera GNS3 2.2 sin VNC.
version: 0.1.0
author: Pablo Rodríguez Garijo (PabloJustDevelops), Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [gns3, networking, cli, mcp, labs]
    related_skills: [gns3-mcp-cli-contract, gns3-pfsense-native]
---

# GNS3 Toolkit Operator

Opera un servidor GNS3 2.2.x desde terminal o agente, sin depender de la GUI ni del VNC.
La misma lógica vive en `cli/gns3lab`, en las tools MCP `gns3_*` y en `gns3core.py`: elige una
vía y no dupliques la misma llamada por dos sitios.

## When to Use

- Crear, arrancar, inspeccionar o verificar laboratorios GNS3 **2.2.x**.
- Configurar topología, consolas, capturas, snapshots, imágenes o plantillas.
- Decidir si una tarea va por `gns3lab`, por el MCP o importando `gns3core`.
- No usar para GNS3 3.x: `/v3` con login por token queda fuera de este cliente.
- Para pfSense por SSH carga `gns3-pfsense-native`; para datos y tools, `gns3-mcp-cli-contract`.

## Elige la vía

| Situación | Vía | Motivo |
|---|---|---|
| Shell, script, una orden puntual, salida completa | `cli/gns3lab` | 46 comandos, `--json`, sin esquemas MCP |
| Agente con el MCP `gns3` conectado | tools `gns3_*` | llamadas tipadas y `gns3_batch` para lecturas |
| Tests o incrustar en Python | `gns3core.py` | núcleo stdlib; devuelve datos, no imprime |
| Varias lecturas independientes | `gns3_batch` | una llamada, resultados indexados y paralelismo |

`gns3core.py` no importa `fastmcp` ni `httpx`. Ninguna función de servidor imprime: imprimir es
responsabilidad de `cli/gns3lab`.

## Procedimiento

1. Comprueba servidor y proyecto antes de tocar nada:
   `gns3lab servers`, `gns3lab status examen-kit` y `gns3lab doctor examen-kit`.
   Criterio: el servidor sale `[OK ]`, el proyecto está abierto y sus nodos aparecen listados.
2. Arranca sólo lo necesario con `gns3lab up examen-kit`. Criterio: cada nodo relevante figura
   como `started`. Arrancar o parar nodos cambia estado: anótalo en el informe final.
3. Entra por consola telnet: `gns3lab exec PC1 "ip dhcp" "show ip" -p examen-kit --idle 4`.
   Criterio: obtienes la salida del comando, no un timeout ni un eco vacío.
4. Si el nodo no tiene consola de texto, usa el monitor QEMU:
   `gns3lab shot PF1 -p examen-kit`, y escribe con `gns3lab type` o `gns3lab key`.
   Criterio: el OCR muestra el cambio esperado; un `shot` sin lectura no es prueba.
5. Verifica con red real: `gns3lab test examen-kit` o un `ping` desde el cliente.
   Criterio: `0% packet loss` y una IP distinta de `0.0.0.0`.
6. Si algo falla, adjunta comando, código de salida y mensaje literal. No traduzcas un fallo a
   «parece que funciona».

## Reglas duras

- **VNC es el último recurso.** Primero `exec` (telnet); después `shot`/`type`/`key`/`mon`
  (HMP). VNC sólo para instaladores con ratón que no aceptan teclado.
- **Ningún secreto en el repo, markdown, commit ni línea de comando.** Las credenciales del
  servidor GNS3 se leen en tiempo de ejecución de `gns3_server.conf`; las de pfSense, sólo de
  variables `PFSENSE_*` exportadas en el entorno.
- **Reporta los cambios de estado**: `up`, `down`, `all`, `server`, `snap`,
  `node start|stop|reload|suspend`, `examen reset`, `upload`, borrar proyectos o arrancar
  `libvirtd`.
- **Verifica con salida real.** Un `200 OK` de la API no prueba conectividad ni configuración.
- **Sólo GNS3 2.2.x.** La 3.x usa `/v3` y login por token; este cliente no sirve.

## Pitfalls

- `screendump` escribe un **PPM** aunque la ruta acabe en `.png`; `shot` lo convierte.
- OCR a escala x1 confunde `w` con `u`: usa x2 y `--psm 4`.
- En HMP la tecla es `ret`, no `enter`; mayúsculas y símbolos van con `shift-<tecla>`.
- La consola del invitado duerme: manda `sendkey shift` antes de la primera tecla útil.
- `POST /templates/{id}` exige `compute_id: local`; `ports_mapping` exige `port_number`.
- `POST /nodes/{id}/files/{ruta}` graba el body en crudo, no un JSON con `content`.
- pfSense con `em0/em1` y `virtio-net-pci` entra en «interface mismatch»: usa `e1000`.

## Verification

```bash
gns3lab doctor examen-kit          # exit 0 y «sin hallazgos»
gns3lab test examen-kit            # bloques sin FALLO; 0% packet loss
gns3lab shot PF1 -p examen-kit     # OCR legible de la pantalla real
```

La tarea está hecha cuando el doctor no tiene hallazgos, la prueba de red da `0% packet loss`
y la salida observada está pegada en el informe. Si un gate no se puede ejecutar, dilo y
propón el comando exacto que falta.
