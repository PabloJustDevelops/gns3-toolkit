---
name: gns3-pfsense-native
description: "Configura pfSense sin VNC: detect, red, DHCP, NAT y SSH."
version: 0.1.0
author: Pablo Rodríguez Garijo (PabloJustDevelops), Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [gns3, pfsense, ssh, dhcp, nat]
    related_skills: [gns3-toolkit-operator, gns3-mcp-cli-contract]
---

# pfSense nativo sin VNC

Configura pfSense por SSH hablando `/conf/config.xml`, sin GUI ni VNC. El VNC queda para un
primer arranque sin SSH; antes se agotan la consola telnet y el monitor HMP.

## When to Use

- Hay que asignar WAN/LAN, IP, DHCP, reglas o NAT a un pfSense dentro de GNS3.
- El firewall repite el menú de asignación o muestra «interface mismatch».
- Ya hay SSH, o se puede habilitar una vez, y quieres una configuración reproducible.
- No usar para pfSense fuera de GNS3 ni para reinstalar el disco: eso es otra tarea.

## Prerequisites

- `gns3lab` en el PATH y el proyecto GNS3 2.2.x abierto.
- Variables exportadas: `PFSENSE_HOST`, `PFSENSE_PORT`, `PFSENSE_USER` y
  `PFSENSE_PASSWORD`. La contraseña es obligatoria; si falta, el error nombra la variable,
  nunca su valor. Host, puerto y usuario tienen valores por defecto.
- Exporta la contraseña sin dejarla en el historial:
  `read -rsp 'Contraseña: ' PFSENSE_PASSWORD; echo; export PFSENSE_PASSWORD`.
- No escribas el valor en el repo, un markdown, un commit ni un comando con el secreto.
- Si aún no hay SSH, habilítalo una vez desde el menú por HMP (`gns3lab shot` para leer,
  `gns3lab type`/`gns3lab key` para responder). El resto del flujo ya usa SSH, no VNC.

## Flujo nativo

1. Detecta las interfaces sin SSH: `gns3lab pf detect -p examen-kit --json`.
   Criterio: devuelve `wan`, `lan` y `adapter_type`. Con `e1000`, espera `em0`/`em1`; con
   `virtio`, espera `vtnet0`/`vtnet1`.
2. Si el disco espera `em0/em1` y el nodo usa `virtio-net-pci`, corrige el adaptador:
   `gns3lab down examen-kit --keep-open`;
   `gns3lab node props PF1 -p examen-kit --set adapter_type=e1000`;
   `gns3lab up examen-kit`.
   Criterio: `pf detect` devuelve `em0`/`em1` y el firewall deja de pedir reassignment.
   Son cambios de estado: anótalos en el informe.
3. Asigna los roles: `gns3lab pf assign --wan em0 --lan em1` (añade `--opt1 <if>` sólo si
   existe OPT1). Criterio: `pf status` muestra WAN y LAN con nombres reales de `ifconfig`.
4. Fija la IP de la LAN: `gns3lab pf ip em1 192.168.1.1 24`. Criterio: `pf status` muestra
   `192.168.1.1` con máscara `255.255.255.0` en `em1`.
5. Define DHCP: `gns3lab pf dhcp em1 192.168.1.100 192.168.1.200`. Criterio: un cliente de
   esa LAN recibe concesión y `show ip` deja de mostrar `0.0.0.0`.
6. Añade la regla de paso antes de cualquier bloqueo:
   `gns3lab pf rule pass --if lan --proto tcp --src any --dst any --port 80`.
   Criterio: `pf status` lista la regla por encima de cualquier `reject`.
7. Activa NAT de salida: `gns3lab pf nat --if wan`. Criterio: `pf status` muestra la regla
   NAT y un cliente alcanza una IP externa.
8. Habilita SSH: `gns3lab pf ssh --port 22022`. Criterio: una conexión SSH al firewall
   responde y `pf status` puede leer versión, interfaces, reglas y rutas.

Para inspeccionar o restaurar la configuración completa:

```bash
gns3lab pf config get > fw.xml
gns3lab pf config put fw.xml --yes
```

`config put` conserva un backup `config.xml.bak-<stamp>`, recarga con `/etc/rc.reload_all` y no
borra las secciones del XML que no entiende.

## Pitfalls

- **VNC no es la vía.** Consola telnet primero; HMP después. El VNC sólo para instaladores.
- `assign` comprueba el nombre contra `ifconfig`; si no existe, devuelve los nombres reales.
  No inventes `em2` ni reutilices el nombre de un puerto de switch.
- No pases un `--opt1` vacío: asigna un rol que no existe. Si no hay OPT1, omite la opción.
- `rule` y `nat` insertan antes de cualquier `reject`; no reordenes reglas a mano en el XML.
- En HMP la tecla es `ret`, no `enter`; usa `shift-<tecla>` para mayúsculas y símbolos.
- La consola del invitado duerme: `type` ya manda `sendkey shift` antes de la primera tecla.
- OCR a escala x1 confunde `w` con `u`: usa x2 y `--psm 4`. `screendump` deja un PPM con
  extensión `.png`.
- Regla rápida del menú: `easyrule pass <if> any any any` exige los cuatro argumentos.
- `gateway=255.255.255.0` en VPCS es la máscara pintada en el campo gateway; `gns3lab test`
  lo detecta y reconfigura. No lo confundas con un fallo de pfSense.

## Errores literales

| Salida | Causa | Arreglo |
|---|---|---|
| `falta la variable de entorno PFSENSE_PASSWORD` | no está exportada | exportarla sin imprimir su valor |
| `adapter_type no soportado o ausente: ...` | nodo sin adaptador reconocible | `pf detect`; fija `e1000` o `virtio-net-pci` |
| error de `assign` con nombres disponibles | la interfaz pedida no está en `ifconfig` | usar un nombre real de `pf detect` |
| `Missing parameters` (`easyrule`) | faltan argumentos en el menú | pasar acción, interfaz, origen y destino |
| `no encuentro el monitor del nodo QEMU` | nodo parado o proceso de otro usuario | `gns3lab up`; `shot` sólo ve el compute local |
| `sin traducción a tecla: [...]` | carácter no ASCII en `type` | ASCII imprimible o `key` con nombre HMP |
| `Port 1/0 for SW1 not found` | puerto de switch pasado como adaptador | el puerto va en `--ppb` del enlace |

## Verification

```bash
gns3lab pf status                       # versión, interfaces, pfctl y rutas reales
gns3lab doctor examen-kit               # exit 0 y «sin hallazgos»
gns3lab exec PC1 "show ip" "ping 192.168.1.1" -p examen-kit --idle 4
```

La prueba es `0% packet loss` en el ping y una IP distinta de `0.0.0.0`. Un `200 OK` de la API
no prueba que la regla, el DHCP o el NAT funcionen. Pega la salida observada en el informe.
