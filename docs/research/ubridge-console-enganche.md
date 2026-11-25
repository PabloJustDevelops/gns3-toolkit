# ubridge: protocolos, consola y vías de enganche

Fecha: 2026-11-25. Objetivo: `~/.local/bin/ubridge`, autorizado por Pablo para análisis
estático. Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-rea`, rama `opencode/rea`.

## Resumen ejecutivo

- El binario es **ubridge 1.3.2**, ELF64 PIE x86-64, no stripped, con símbolos C legibles.
  SHA-256: `b72944a4c895b36349db9de0b667f94941c0ad5988111a1b76b8b1d6ea3f326c`.
- Su función principal es **reenviar tramas L2 entre dos NIOs**. UDP y UNIX datagram son
  transportes de NIO; TCP y UNIX stream son transportes del **hipervisor de control**.
  pcap/libpcap aparece en capturas y en NIOs Ethernet.
- **No hay evidencia estática de Telnet, VNC/RFB, WebSocket, HTTP ni servidor de consola**.
  Las búsquedas de símbolos y cadenas no devolvieron coincidencias. La consola Telnet y el
  proxy WebSocket pertenecen a `gns3server`, no a ubridge.
- `hypervisor reset` **borra todos los bridges**, no reinicia una consola. El endpoint
  `/console/reset` de GNS3, en QEMU 2.2.61, reinicia el proxy Telnet; tampoco reinicia el
  invitado.
- La vía recomendada para este repo es **API v2 de GNS3** (controller para consola y
  compute para NIO/captura), no hablar directamente con el proceso ubridge: crear/borrar
  NIO UDP, capturar un puerto y reiniciar el proxy de consola tienen endpoints, mientras el
  puerto del hipervisor ubridge es efímero y no aparece en la API del nodo.

## Método y niveles de confianza

Se usaron `file`, `sha256sum`, `nm`, `readelf`, `objdump`, `strings`, `rztriage info/imports/
strings/funcs/disasm/decomp` y lectura de la fuente instalada de GNS3 2.2.61
(`gns3server/version.py:26`). **No se ejecutó ubridge**, no se abrieron puertos, no se
hicieron capturas de proceso y no se lanzó el autoanálisis de Ghidra. Los pseudocódigos son
de decompilación local por función.

Leyenda:

- **Observado (alta)**: sale directamente de una herramienta o de una línea de fuente citada.
- **Inferencia (media)**: composición de varias observaciones; no es prueba de ejecución.
- **Desconocido/bajo**: no se puede afirmar con análisis estático o sin cambiar estado.

No se usó REA/Ghidra formal, por lo que no hay `evidence_id`. Las citas son comandos y
direcciones reproducibles sobre el SHA-256 anterior.

## 1. Identificación del binario

### Gates literales

```text
$ sha256sum ~/.local/bin/ubridge
b72944a4c895b36349db9de0b667f94941c0ad5988111a1b76b8b1d6ea3f326c  /home/pablorg/.local/bin/ubridge

$ file ~/.local/bin/ubridge
/home/pablorg/.local/bin/ubridge: ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV), dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2, BuildID[sha1]=cd124c6c83c099822eeb11f4d8b931a4e5ee1fab, for GNU/Linux 6.1.0, not stripped

$ rztriage info ~/.local/bin/ubridge 2>&1 | head -12
arch     x86
cpu      N/A
features N/A
baddr    0x00000000
binsz    0x0004575d
bintype  elf
bits     64
class    ELF64
compiler GCC: (GNU) 16.2.1 20260810
dbg_file N/A
endian   LE
hdr.csum N/A

$ rztriage imports ~/.local/bin/ubridge 2>&1 | head -20
nth      vaddr bind   type   lib name
-------------------------------------------------------------
  1 0x00005030 GLOBAL FUNC       pthread_setcancelstate
  2 0x00005040 GLOBAL FUNC       pthread_join
  3 0x00005050 GLOBAL FUNC       pcap_dump_flush
  4 0x00005060 GLOBAL FUNC       pthread_cond_destroy
  5 0x00005070 GLOBAL FUNC       pthread_condattr_setclock
  6 0x00005080 GLOBAL FUNC       printf
  7 0x00005090 GLOBAL FUNC       memset
  8 0x000050a0 GLOBAL FUNC       pcap_findalldevs
  9 0x000050b0 GLOBAL FUNC       snprintf
 10 0x000050c0 GLOBAL FUNC       pcap_sendpacket
 11 0x000050d0 GLOBAL FUNC       shutdown
 12 0x000050e0 GLOBAL FUNC       inet_pton
 13 0x000050f0 GLOBAL FUNC       pthread_sigmask
 14 0x00005100 GLOBAL FUNC       close
 15 0x00005110 GLOBAL FUNC       ioctl
 16 0x00005120 GLOBAL FUNC       strncat
 17 0x00005130 GLOBAL FUNC       pcap_close
 18 0x00005140 GLOBAL FUNC       clock_gettime
```

Los cuatro comandos terminaron con código 0 en esta sesión. En los dos pipelines, `head`
también terminó con 0.

### Cabecera ELF y dependencias

`readelf -h` devolvió:

```text
Encabezado ELF:
  Mágico:  7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00
  Clase:                             ELF64
  Datos:                              complemento a 2, little endian
  Version:                           1 (current)
  OS/ABI:                             UNIX - System V
  Versión ABI:                        0
  Tipo:                               DYN (Position-Independent Executable file)
  Máquina:                            Advanced Micro Devices X86-64
  Versión:                            0x1
  Dirección del punto de entrada:    0x5a30
  Inicio de encabezados de programa: 64  (bytes)
  Inicio de encabezados de sección:  284512  (bytes)
  Opciones:                           0x0
  Size of this header:               64  (bytes)
  Size of program headers:           56  (bytes)
  Number of program headers:         16
  Size of section headers:           64  (bytes)
  Number of section headers:         33
  Section header string table index: 32
```

`readelf -dW` muestra:

```text
NEEDED  libpcap.so.1
NEEDED  libm.so.6
NEEDED  libc.so.6
FLAGS_1 Opciones: PIE
```

`ls -l` informa de un ejecutable de 286624 bytes. `getcap` devuelve
`cap_net_admin,cap_net_raw=ep`, coherente con la manipulación de interfaces host. El stack
es `RW` (no ejecutable) y hay `GNU_RELRO`. Estos datos son **observados, confianza alta**.

### Símbolos relevantes

Salida real de `nm -C -S --defined-only ~/.local/bin/ubridge`, filtrada a las funciones que
sostienen las conclusiones:

```text
0000000000006144 000000000000080e t bridge_nios
0000000000007e68 0000000000000155 T create_nio_udp
00000000000081b5 00000000000001ba T create_nio_unix
000000000000bd05 00000000000001c0 T create_pcap_capture
000000000000c629 0000000000000181 T hypervisor_send_reply
000000000000ce15 0000000000000272 t hypervisor_thread
000000000000c0e2 00000000000002ce t ip_listen
0000000000005b29 000000000000008d T main
0000000000005d02 000000000000031f T parse_cli_args
000000000000d44b 000000000000058b T run_hypervisor
0000000000007227 0000000000000283 T run_ubridge
0000000000006fb7 0000000000000025 T ubridge_reset
00000000000079f0 00000000000003bc t udp_connect
000000000000c3b0 0000000000000200 t unix_listen
000000000000ef93 0000000000000196 t cmd_add_nio_udp
000000000000fe66 0000000000000186 t cmd_start_capture_bridge
000000000000ca28 0000000000000044 t cmd_reset
```

Hay nombres duplicados para módulos distintos (por ejemplo `cmd_create_bridge` en
`0xe1e3` y `0x14502`). Las direcciones de esta tabla corresponden al módulo `bridge`
principal, verificado contra `bridge_cmd_array`.

### Imports y cadenas

Imports relevantes observados con `rztriage imports`:

```text
pcap_findalldevs, pcap_open_live, pcap_next_ex, pcap_sendpacket,
pcap_compile, pcap_setfilter, pcap_open_dead, pcap_dump_open, pcap_dump,
pcap_dump_flush, pcap_dump_close, socket, bind, connect, listen, accept,
send, sendto, sendmsg, recvfrom, recvmsg, select, getaddrinfo,
pthread_create, getuid, getsockopt, umask, unlink
```

Cadenas relevantes de `rztriage strings`:

```text
0x0002b070  Usage: %s [OPTION] ... -H [<ip_address>:]<tcp_port> : Hypervisor mode over TCP
                                      -U <socket_path> : Hypervisor mode over UNIX socket (recommended)
0x0002b2a6  1.3.2
0x0002b778  UDP tunnel connecting from local port %d to IPv%d address %s on port %d
0x0002b820  create_unix_socket: socket
0x0002b83b  create_unix_socket: bind
0x0002bc17  pcap_protocol
0x0002bc25  pcap_file
0x0002bc30  Starting packet capture to %s with protocol %s
0x0002c488  Hypervisor control socket started (%s).
0x0002c4b8  Hypervisor: unable to create TCP sockets.
0x0002c4e8  Hypervisor TCP control server started (IP %s port %d).
```

Búsquedas directas sin coincidencias (exit code 1):

```text
$ strings -a -n 4 ~/.local/bin/ubridge | grep -Ei 'telnet|vnc|rfb|websocket|console|serial'
$ nm -C -S --defined-only ~/.local/bin/ubridge | grep -Ei 'telnet|vnc|rfb|websocket|console|serial'
```

Esto prueba **ausencia de esos nombres en las tablas de símbolos y cadenas**, no una
imposibilidad lógica absoluta. Sin embargo, el código decompilado tampoco muestra un parser
de esos protocolos: el camino de datos es `nio_recv -> filtros -> pcap -> delay line (si
hay filtro de retardo) -> nio_send`.

## 2. Protocolos y transportes

| Capacidad | Estado | Evidencia | Confianza |
|---|---|---|---|
| UDP NIO | Sí, datagramas crudos entre puertos locales/remotos | `create_nio_udp`, `udp_connect`, `nio_udp_send/recv`; `socket(..., SOCK_DGRAM, ...)`, `bind`, `connect`, `send`, `recvfrom` | Alta |
| TCP | Sí, sólo control del hipervisor `-H` | `ip_listen` pide `SOCK_STREAM`; `run_hypervisor` hace `select/accept`; no hay `create_nio_tcp` | Alta |
| UNIX stream | Sí, control del hipervisor `-U` | `unix_listen`: `socket(AF_UNIX, SOCK_STREAM, 0)`, `bind`, `listen`; `peer_allowed` compara UID | Alta |
| UNIX datagram | Sí, NIO | `create_unix_socket`: `socket(AF_UNIX, SOCK_DGRAM, 0)`; `nio_unix_send` usa `sendto` | Alta |
| pcap | Sí, archivo de captura y acceso a interfaces Ethernet | imports libpcap; `create_pcap_capture`, `pcap_capture_packet`; `capture_start` abre `AF_PACKET/SOCK_RAW` | Alta |
| Ethernet/TAP/Linux RAW | Sí, NIOs | `create_nio_ethernet`, `create_nio_tap_with_carrier`, `create_nio_linux_raw`; `/dev/net/tun`, `PACKET_ADD_MEMBERSHIP` | Alta |
| Telnet | No observado | cero coincidencias en símbolos/cadenas; GNS3 implementa su proxy Telnet fuera de ubridge | Alta para “no observado”; media para “no implementado” |
| VNC/RFB | No observado | cero coincidencias; no hay framebuffer ni parser RFB en los caminos decompilados | Alta para “no observado”; media para “no implementado” |
| WebSocket/HTTP | No observado | cero coincidencias; el bridge WebSocket está en `gns3server/compute/base_node.py` | Alta |

`gso_tcp_init` y `gso_tcp_next` aparecen en símbolos, pero son utilidades de segmentación
TCP dentro del procesamiento de paquetes; no crean un socket TCP ni un NIO TCP.

### 2.1 Hipervisor de control

`parse_cli_args` acepta `-H [ip:]puerto` y `-U socket`. En modo `-H`, si el puerto queda a
cero, `run_hypervisor` usa `0x1092` = **4242**; `parse_cli_args` fija `127.0.0.1` cuando `-H`
no incluye IP. Sin `-H` ni `-U` se ejecuta el modo de configuración INI, no el hipervisor.
GNS3 no usa ese puerto fijo: elige uno libre y lanza `ubridge -H host:puerto`
(`gns3server/ubridge/hypervisor.py:254-264`).

El protocolo es textual, una línea por comando:

```text
módulo comando arg1 arg2 ...
```

`hypervisor_thread` lee con `fgets(..., 512, ...)`, tokeniza con `parser_scan_buffer`, exige
al menos módulo y comando, y despacha bajo un mutex global. `hypervisor_exec_cmd` valida
módulo, comando y número de parámetros.

Las respuestas se construyen en `hypervisor_send_reply` con `"%3d%s"` y `"\r\n"`. El
separador es espacio para líneas intermedias y `-` para la última. Los bytes observados en
`0x2c229/0x2c22b` son `-\0` y ` \0`. Códigos observados: `100` éxito/final, `101` información
intermedia y `2xx` error. El cliente Python instalado confirma ese contrato en
`gns3server/ubridge/ubridge_hypervisor.py:186-197,252-271`.

Seguridad observada:

- En modo UNIX, `run_hypervisor` llama a `peer_allowed`; éste usa `SO_PEERCRED` y sólo acepta
  si el UID del cliente coincide con el proceso. `unix_listen` aplica `umask(077)`.
- En modo TCP **no hay autenticación**: la rama `peer_allowed` sólo se ejecuta cuando se usa
  `-U`. El bind por defecto a loopback reduce el riesgo, pero exponer `-H 0.0.0.0:...`
  convertiría el control en una superficie sin auth. **Confianza alta**.

### 2.2 UDP NIO

`cmd_add_nio_udp` recibe cuatro parámetros:

```text
bridge add_nio_udp <bridge> <lport> <rhost> <rport>
```

`create_nio_udp(lport, rhost, rport)` crea el NIO y llama a `udp_connect`. Éste resuelve
IPv4/IPv6 con `getaddrinfo`, crea `SOCK_DGRAM`, hace `bind` al puerto local y `connect` al
remoto. `nio_udp_send` usa `send`; `nio_udp_recv` usa `recvfrom`. No hay serialización ni
framing de aplicación: se mueven datagramas/tramas tal cual.

Un bridge sólo admite dos NIOs y debe estar parado para borrar un NIO UDP. Para cambiar el
triplete `lport/rhost/rport` hace falta `stop -> delete_nio_udp -> add_nio_udp -> start`.
**Confianza alta** (`cmd_delete_nio_udp` rechaza el bridge si está running).

### 2.3 UNIX socket

Hay dos roles distintos:

1. **Control**: `-U`, socket stream, escucha, acepta conexiones y comprueba UID.
2. **NIO**: `bridge add_nio_unix <bridge> <local_file> <remote_file>`, socket datagram; se
   hace `bind` al fichero local y `sendto` al remoto.

La fuente GNS3 instalada define `nio_unix` en el schema, pero no contiene llamadas a
`bridge add_nio_unix`; el camino habitual de QEMU es UDP. El NIO UNIX existe, pero su uso en
esta topología concreta queda **no verificado**.

### 2.4 pcap y capturas

Hay dos mecanismos:

- `bridge start_capture <bridge> <fichero> [protocolo]` crea un pcap con `pcap_open_dead` y
  `pcap_dump_open`; por defecto el protocolo es `EN10MB`. `bridge_nios` llama a
  `pcap_capture_packet` antes de reenviar la trama.
- `capture start_kernel <interfaz> <fichero> [protocolo]` usa un socket
  `AF_PACKET/SOCK_RAW/ETH_P_ALL`, `PACKET_ADD_MEMBERSHIP`, `SO_RCVTIMEO` y
  `SO_TIMESTAMPNS`; el hilo lee `SCM_TIMESTAMPNS` y entrega paquetes a pcap. Esta segunda
  vía requiere privilegios de captura host. `PACKET_AUXDATA` pertenece al NIO Linux RAW
  (`nio_linux_raw_open_socket`), no a `capture start_kernel`.

Para GNS3, el endpoint de captura de puerto QEMU acaba enviando exactamente
`bridge start_capture QEMU-<node_id>-<adapter> "<output_file>"`
(`gns3server/compute/qemu/qemu_vm.py:1565-1599`). **Confianza alta**.

### 2.5 Telnet, VNC y “reset de consola”

La consola Telnet de QEMU la arranca el propio QEMU con
`-serial telnet:127.0.0.1:<puerto>,server,nowait` (`qemu_vm.py:1688-1692`). GNS3 añade un
proxy `AsyncioTelnetServer` y el bridge WebSocket (`base_node.py:371-426,428-479`). Nada de
ese recorrido pasa por ubridge. Para VNC, QEMU recibe `-vnc <host>:<puerto>`
(`qemu_vm.py:1695-1699`); tampoco interviene ubridge.

En QEMU 2.2.61, `reset_console()` llama a `reset_wrap_console()` sólo si el proceso está
corriendo (`qemu_vm.py:1658-1664`), y `reset_wrap_console()` para y vuelve a arrancar el
proxy Telnet (`base_node.py:420-426`). Es un **reset de la conexión/proxy**, no del invitado.
Para VNC, ese wrapper no aplica porque exige `console_type == "telnet"`.

`hypervisor reset` es otra cosa: `ubridge_reset()` llama a `free_bridges` y
`free_iol_bridges`. Borra la topología ubridge, no reinicia consolas. El pseudocódigo de
`rztriage decomp ~/.local/bin/ubridge ubridge_reset` es:

```c
void sym.ubridge_reset(void)
{
    sym.free_bridges(_obj.bridge_list);
    sym.free_iol_bridges(_obj.iol_bridge_list);
}
```

## 3. Superficie de comandos del hipervisor

Los arrays se decodificaron desde `.data` con entradas de 32 bytes; el stride `0x20` se ve en
`hypervisor_register_cmd_array`. Esta es la superficie estática principal:

```text
[hypervisor]
version 0/0; module_list 0/0; cmd_list 1/1; reset 0/0; close 0/0; stop 0/0

[bridge]
create 1/1; delete 1/1; start 1/1; stop 1/1; show 1/1; get_stats 1/1;
reset_stats 1/1; rename 2/2; add_nio_udp 4/4; remove_nio_udp 4/4;
delete_nio_udp 4/4; add_nio_unix 3/3; add_nio_tap 2/3; delete_nio_tap 2/2;
set_nio_tap_carrier 2/2; add_nio_ethernet 2/2; add_nio_linux_raw 2/2;
start_capture 2/3; stop_capture 1/1; add_packet_filter 2/10;
delete_packet_filter 2/2; reset_packet_filters 1/1; enable_packet_filter 3/3;
set_pcap_filter 1/2; list 0/0

[capture]
start_kernel 2/3; stop_kernel 0/1; status 0/0
```

También hay módulos `docker`, `iol_bridge`, `brctl`, `link`, `vxlan`, `tap`, `tc` y
`marker`. Exponen administración de interfaces Linux, bridges, VLAN, veth, VXLAN y filtros.
No amplían la conclusión sobre consolas: siguen siendo tramas/red, no protocolos de terminal.

## 4. Propuesta concreta para `gns3-toolkit`

### 4.1 Recomendación: API primero

Operar la API GNS3 mantiene coherentes el nodo, el NIO, el bridge ubridge y los ficheros de
captura. Hablar directamente con ubridge puede dejar el estado de GNS3 desincronizado y
requiere descubrir un puerto efímero que la API no publica. Las rutas de consola son del
**controller**; las de NIO, captura de puerto y reserva UDP son de la API **compute**.

| Operación propuesta | Endpoint GNS3 real | `gns3core.py` hoy | Trabajo futuro recomendado |
|---|---|---|---|
| Crear NIO UDP | `POST /v2/compute/projects/{pid}/qemu/nodes/{nid}/adapters/{adapter}/ports/{port}/nio` | Sólo `post()` genérico (`gns3core.py:136`) | Añadir `node_nio_udp_create()` o `node_nio(..., action="create")` contra la API compute |
| Actualizar filtros/suspend | `PUT` en la misma ruta compute | Sólo `put()` genérico (`gns3core.py:142`) | Añadir `node_nio_update()`; **no** prometer cambio de `lport/rhost/rport` |
| Borrar NIO | `DELETE` en la misma ruta compute | Sólo `delete()` genérico (`gns3core.py:145`) | Añadir `node_nio_delete()` |
| Capturar puerto | `POST /v2/compute/.../ports/{port}/start_capture` y `stop_capture` | `link_capture()` sólo cubre enlaces del controller (`gns3core.py:301`) | Añadir `node_port_capture()` contra la API compute |
| Descargar pcap | `GET /v2/compute/.../ports/{port}/pcap` | `link_capture("pcap")` sólo cubre enlaces (`gns3core.py:310`) | Añadir `node_port_capture("pcap")` con `raw=True` |
| Reiniciar proxy de consola | `POST /v2/projects/{pid}/nodes/{nid}/console/reset` | **Ya existe** `Client.console_reset()` (`gns3core.py:351`) | Añadir consumidor CLI/MCP; documentar que no reinicia el invitado |
| Reset de todas las consolas | `POST /v2/projects/{pid}/nodes/console/reset` | No hay wrapper | Añadir `console_reset_all()` si se necesita |
| Reservar puerto UDP | `POST /v2/compute/projects/{pid}/ports/udp` (sin body; devuelve `udp_port`) | `Client.udp_port()` apunta a `/v2/computes/local/ports/udp` y manda body: ruta no verificada/incorrecta para 2.2.61 (`gns3core.py:494`) | Corregir a `allocate_udp_port(pid)` contra la API compute |
| Abrir consola | `GET /v2/projects/{pid}/nodes/{nid}/console/ws` | `console_ws_url()` (`gns3core.py:354`) y `console_for()` (`gns3core.py:773`) | Telnet directo ya funciona; VNC sigue fuera de ubridge |

Las rutas relativas están en `orchestration/inventario-rutas-gns3.txt` (líneas 167-172,
181-182, 306-308 y 142). `Route._route` añade `/v2` a los handlers de controller y
`/v2/compute` a los de compute (`gns3server/web/route.py:141-147`). No existe una ruta del
controller `/v2/projects/.../adapters/.../nio`; para NIO/captura hay que usar la API compute
o un cliente específico de compute.

Contratos CLI/MCP sugeridos, sin implementar en este carril:

```text
gns3lab nio <nodo> <adapter> create --lport N --rhost H --rport N
gns3lab nio <nodo> <adapter> delete
gns3lab capture-port <nodo> <adapter> start|stop|pcap
gns3lab console-reset <nodo>
```

Estos contratos deben resolver el compute del nodo (`compute_id`/URL) para `nio` y
`capture-port`; `console-reset` usa el controller. No deben asumir que todas las rutas
cuelgan del mismo prefijo.

Body mínimo para QEMU, validado por `gns3server/schemas/nio.py:26-56`:

```json
{"type":"nio_udp","lport":10000,"rhost":"127.0.0.1","rport":20000}
```

Body mínimo de captura para QEMU 2.2.61 (`schemas/node.py:79-96`):

```json
{"capture_file_name":"captura.pcap"}
```

El schema acepta `data_link_type`, pero el handler QEMU sólo usa `capture_file_name`
(`qemu_handler.py:387-394`) y ubridge fija `EN10MB` cuando no recibe protocolo. Por eso no se
promete cambio de DLT desde esta ruta.

Detalle importante: el handler QEMU sólo acepta `nio_udp` al crear
(`qemu_handler.py:293-319`) y su `PUT` sólo aplica `filters` y `suspend`
(`qemu_handler.py:337-349`). Cambiar los extremos UDP requiere borrar y recrear el NIO.

### 4.2 Sólo diagnóstico directo, si hace falta

Un futuro tool de bajo nivel podría conectarse al hipervisor existente y ejecutar comandos
de lectura (`hypervisor version`, `bridge list`, `bridge show`, `bridge get_stats`). Para
ello habría que:

1. localizar el proceso ubridge del nodo leyendo `/proc/<pid>/cmdline` y `/proc/<pid>/cwd`;
2. extraer el puerto de `-H` y comprobar que el cwd coincide con `node_directory`;
3. limitar conexiones a loopback/mismo usuario y no exponer un comando arbitrario.

Esto **no requiere parchear el binario**, pero sí código nuevo y pruebas de ciclo de vida.
No se recomienda como interfaz principal: el puerto es efímero, TCP no autentica y un reset
o delete directo no actualiza el estado del controller. Tampoco conviene exponer un tool
MCP con comandos ubridge arbitrarios: la misma superficie permite crear/borrar interfaces,
capturar tráfico host y borrar bridges. Si `Server.host` de GNS3 es `0.0.0.0` o `::`, hay que
comprobar el firewall: el proceso ubridge hereda ese host y su control TCP no tiene auth.

## 5. Qué no se puede hacer sin parchear ubridge

Con el binario actual no se puede:

- convertir tramas/serial en Telnet, implementar negociación Telnet o servir VNC/RFB;
- reiniciar una consola o un invitado mediante `hypervisor reset` o cualquier comando de
  bridge;
- crear un NIO TCP o un transporte de consola que no existe;
- añadir autenticación al control TCP; la alternativa sin parche es bind a loopback o un
  lanzamiento propio con `-U`;
- inyectar una trama arbitraria mediante un comando de ubridge: habría que usar el extremo
  UDP de un NIO, no un comando de consola;
- cambiar el launch de GNS3 de `-H` a `-U` sin tocar configuración/código del servidor
  (aunque no sea un parche del binario).

Sí se puede, sin parche y mediante la API de GNS3: crear/borrar NIOs UDP, capturar puertos,
consultar estadísticas del nodo y reiniciar el proxy Telnet. Reiniciar el invitado es una
operación del emulador (por ejemplo `system_reset` por HMP o stop/start del nodo), no de
ubridge.

## 6. Límites y confianza final

- **Alta**: identidad/hash, símbolos, imports, protocolo textual, transports UDP/UNIX/TCP,
  semántica de `hypervisor reset`, superficie de comandos y cobertura actual de
  `gns3core.py`.
- **Media**: mapeo exacto entre endpoints de GNS3 2.2.61 y comandos ubridge, porque se basa
  en la fuente instalada y en decompilación, no en una sesión de tráfico.
- **Baja/desconocido**: comportamiento bajo carga, compatibilidad con otras versiones de
  ubridge/GNS3, estado real de los procesos y puertos de esta máquina, y uso práctico del
  NIO UNIX. No se ejecutó el binario ni se modificó estado fuera de esta sesión.

## Reproducción mínima

```bash
sha256sum ~/.local/bin/ubridge
file ~/.local/bin/ubridge
nm -C -S --defined-only ~/.local/bin/ubridge
readelf -h ~/.local/bin/ubridge
readelf -dW ~/.local/bin/ubridge
rztriage info ~/.local/bin/ubridge
rztriage imports ~/.local/bin/ubridge
rztriage strings ~/.local/bin/ubridge
rztriage decomp ~/.local/bin/ubridge run_hypervisor
rztriage decomp ~/.local/bin/ubridge hypervisor_thread
rztriage decomp ~/.local/bin/ubridge udp_connect
rztriage decomp ~/.local/bin/ubridge create_nio_unix
rztriage decomp ~/.local/bin/ubridge create_pcap_capture
rztriage decomp ~/.local/bin/ubridge bridge_nios
rztriage decomp ~/.local/bin/ubridge ubridge_reset
```
