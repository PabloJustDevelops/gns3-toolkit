# Comandos de `gns3lab`

Referencia de los 46 subcomandos que registra `cli/gns3lab`. Las líneas `usage` están copiadas
de `gns3lab <cmd> --help`; los ejemplos suponen el servidor local y el proyecto `examen-kit`.

Índice: [Convenciones](#convenciones) · [Servidor](#servidor-y-diagnóstico) ·
[Proyectos](#proyectos) · [Catálogo](#catálogo-y-computes) · [Topología](#topología) ·
[Consola](#consola-y-pantalla) · [pfSense](#pfsense) · [Ficheros](#ficheros-y-discos).

## Convenciones

- `--server`, `-s`: servidor configurado. Es global y va **antes** del subcomando:
  `gns3lab -s clase status`.
- `--json`: salida parseable uniforme, también global y antes del subcomando:
  `gns3lab --json status`. Si el handler ya imprime JSON se respeta; si no, se envuelve como
  `{"cmd", "ok", "output"}`. `stderr` no se captura y el exit code se conserva.
- Proyecto: nombre parcial, prefijo del `project_id`, o nada si hay uno solo abierto. Con varios
  abiertos hay que nombrarlo; la config puede traer un `matcher` para desempatar.
- Credenciales del servidor `local`: se leen de `~/.config/GNS3/2.2/gns3_server.conf` en tiempo
  de ejecución. Las de pfSense salen del entorno (`PFSENSE_*`), nunca de un fichero del repo.
- Códigos de salida: `0` correcto; `1` fallo de nodo, enlace o comprobación; `2` servidor que no
  responde en los comandos que lo comprueban (`status`, `doctor`, `examen`, `watch`).

Los comandos que cambian estado fuera de la sesión (`up`, `down`, `all`, `server`, `snap`,
`node start|stop|reload|suspend`, `examen reset`) deben reportarse en el informe de la tarea.

## Servidor y diagnóstico

### `servers`

```text
usage: gns3lab servers [-h]
```

Lista los servidores de la config, si responden, su versión, proyectos y auth.

```bash
gns3lab servers
```

Confirma una línea `[OK ]` por servidor alcanzable; `[NO ]` si no contesta.

### `status`

```text
usage: gns3lab status [-h] [project]
```

Proyectos, cuál se seleccionaría, y para ese los nodos con estado y consola.

```bash
gns3lab status examen-kit
```

Confirma `* examen-kit ... abierto` y una línea por nodo con `started` y `telnet:<puerto>` o
`vnc:<puerto>`. Sale con código 2 si el servidor no responde.

### `up` / `down`

```text
usage: gns3lab up [-h] [project]
usage: gns3lab down [-h] [--keep-open] [project]
```

`up` abre el proyecto y arranca lo que no esté `started`; `down` para los nodos y cierra salvo
`--keep-open`.

```bash
gns3lab up examen-kit
gns3lab down examen-kit --keep-open
```

### `test`

```text
usage: gns3lab test [-h] [project]
```

Conectividad real por las consolas de las VPCS: lee IP y gateway, corrige la gateway cuando VPCS
pinta la máscara y hace ping entre PCs, a la gateway y a `8.8.8.8`.

```bash
gns3lab test examen-kit
```

Confirma bloques `gateway` y `conectividad` sin ningún `FALLO`. La prueba es `0% packet loss`.

### `doctor`

```text
usage: gns3lab doctor [-h] [--json] [--check-updates] [project]
```

Chequeo integral: servidor y versión, computes, binarios (`tesseract`, `qemu-img`, `tshark`,
`sshpass`), `libvirtd`, Pillow, proyecto, nodos, monitor HMP, discos compartidos y nodo NAT.
Con `--check-updates` añade si hay versión nueva; sin el flag no toca la red.

```bash
gns3lab doctor examen-kit
gns3lab --json doctor examen-kit
gns3lab doctor --check-updates --json
```

Confirma un bloque `resumen` con `sin hallazgos` y código 0. Cada línea `- ...` es un problema.
Código 2 si el servidor no responde.

### `stats`

```text
usage: gns3lab stats [-h] [--json]
```

CPU, memoria, disco, carga y swap de cada compute (`GET /v2/statistics`).

```bash
gns3lab stats
```

### `version-v1`

```text
usage: gns3lab version-v1 [-h] [--json]
```

Versión del servidor por el puente antiguo `GET /v1/version`. Para saber qué controller hay
delante, usa `servers` o `status` (`/v2/version`).

```bash
gns3lab version-v1
```

### `examen`

```text
usage: gns3lab examen [-h] [--name NAME] [--from FROM_PROJECT] [--json]
                      [--dest DEST] [--idle IDLE] [--yes]
                      {setup,verify,reset,informe}
```

- `setup`: monta el kit (pfSense, switch, NAT y clientes) desde plantillas e imágenes del
  servidor. `--from` toma disco y adaptador de un proyecto local.
- `verify`: comprueba nodos, enlaces y conectividad. `--idle` ajusta la quietud del ping.
- `reset`: reinicia el kit; exige `--yes`.
- `informe`: escribe un Markdown en `~/GNS3/informes/` con topología, estado y comprobaciones.
  `--server local|clase` elige el servidor; `--dest` la ruta.

```bash
gns3lab examen setup --name "Kit de examen"
gns3lab examen verify --name "Kit de examen"
gns3lab examen informe --server clase --name "Pablo Rodriguez"
```

`setup` y `reset` cambian estado: se reportan. `informe` sólo lee.

## Proyectos

### `new`

```text
usage: gns3lab new [-h] name
```

Crea un proyecto vacío y lo abre. El `path` que manda es `$HOME/GNS3/projects/<nombre>` del
usuario que ejecuta la CLI; en un servidor remoto puede no existir.

```bash
gns3lab new examen
```

Confirma `examen creado (xxxxxxxx), abierto=True`.

### `export` / `import`

```text
usage: gns3lab export [-h] dest [project]
usage: gns3lab import [-h] file [name]
```

`export` descarga el `.gns3p` (zip); el fichero debe empezar por `PK`. `import` corrige el paquete
antes de subirlo: quita nodos `cloud`, activa `linked_clone`, sustituye discos ausentes por un
`empty*.qcow2` si lo hay, arregla tags de Docker, añade NAT si falta y pasa `startup.vpc` a
`ip dhcp`.

```bash
gns3lab export ~/GNS3/exports/examen.gns3p examen
gns3lab import ~/GNS3/exports/examen.gns3p examen-copia
```

El export no lleva las imágenes de disco.

### `fix`

```text
usage: gns3lab fix [-h] [--keep-both] [project]
```

Exporta, reescribe el `.gns3` en disco, reimporta con id nuevo y, salvo `--keep-both`, borra el
proyecto roto y devuelve el nombre original. No aplica las correcciones de WAN ni de
`startup.vpc` que sí hace `import`.

### `port`

```text
usage: gns3lab port [-h] [--from FROM_SERVER] [--name NAME] [--start]
                    [--no-compress]
                    [project]
```

Porta un proyecto entre servidores: para el origen, exporta, sube los discos que falten
(comprimidos con `qemu-img convert -c` si son qcow2), aplica las correcciones de `import`,
importa, renombra y, con `--start`, arranca.

```bash
gns3lab -s clase port examen-kit --from local --name "Pablo Rodriguez" --start
```

Los discos se suben al compute `local` del destino. Si origen y destino son el mismo servidor,
aborta.

### `project`

```text
usage: gns3lab project [-h] [-p PROJECT] [--content CONTENT] [--json] [--yes]
                       {duplicate,load,stats,file} [target] [path]
```

| Acción | Uso |
|---|---|
| `duplicate <nombre>` | clona el proyecto (export + import en el servidor) |
| `load <ruta>` | carga un `.gns3` desde una ruta del servidor |
| `stats` | nodos, enlaces y estado de recursos |
| `file get <ruta>` | lee un fichero del proyecto |
| `file put <ruta> --content TEXTO` | escribe y **verifica** leyendo de vuelta |

```bash
gns3lab project stats -p examen-kit
gns3lab project file get project.gns3 -p examen-kit
gns3lab project file put notas.txt --content "hola" -p examen-kit
```

## Catálogo y computes

### `compute`

```text
usage: gns3lab compute [-h] [--json] [--set SET] [--emulator EMULATOR]
                       [--remote-action REMOTE_ACTION] [--yes]
                       [action] [cid] [emulator_arg] [remote_arg]
```

Sin acción lista computes; con id o nombre muestra detalle. Acciones: `add`, `update`, `rm`,
`ports`, `idlepc`, `action` (pasarela al compute: `binaries`, `img`…). `rm` exige `--yes`.

```bash
gns3lab compute
gns3lab compute local
gns3lab compute ports local
gns3lab compute action local qemu binaries
```

### `emulator`

```text
usage: gns3lab emulator [-h] [--port PORT] [--json]
                        {qemu-binaries,qemu-capabilities,docker-images,interfaces,ports,udp}
```

Datos del compute local. `udp --port N` reserva un puerto UDP.

```bash
gns3lab emulator qemu-capabilities
gns3lab emulator interfaces
gns3lab emulator udp --port 10000
```

### `images`

```text
usage: gns3lab images [-h] [--emulator EMULATOR] [--json]
```

Imágenes del compute local; `--emulator` acepta `qemu` (por defecto), `docker`, `iou`…

```bash
gns3lab images
gns3lab images --emulator docker
```

Lista vacía suele significar que el compute no responde.

### `templates` / `template`

```text
usage: gns3lab templates [-h]
usage: gns3lab template [-h] [--content CONTENT] [--json]
                        [--from-node FROM_NODE] [--type TYPE] [--name NAME]
                        [--console CONSOLE] [--set SET] [-p PROJECT] [--yes]
                        {list,create,update,delete,duplicate,base-config}
                        [target] [filename]
```

`template create` acepta `--from-node` (copia tipo y properties de un nodo) o `--type`;
`--console` fija el puerto en la plantilla, que es donde la API sí lo aplica.
`base-config` lista o lee/escribe `filename` con `--content`.

```bash
gns3lab templates
gns3lab template create --name "pfSense lab" --from-node PF1 -p examen-kit
gns3lab template update "pfSense lab" --set console=5902
gns3lab template duplicate "pfSense lab" --name "pfSense copia"
gns3lab template base-config "pfSense lab"
```

### `symbols` / `symbol`

```text
usage: gns3lab symbols [-h] [--filter FILTER] [--json]
usage: gns3lab symbol [-h] [--file FILE] [--output OUTPUT] [--json]
                      {dimensions,raw,default,upload} [symbol]
```

`symbols` lista y filtra por texto en id, fichero o tema. `symbol raw <id>` descarga el SVG;
`--output` lo guarda; `upload <id> --file <ruta>` lo sube. El id tiene la forma
`:/symbols/cloud.svg`.

```bash
gns3lab symbols --filter router
gns3lab symbol dimensions ":/symbols/cloud.svg"
gns3lab symbol raw ":/symbols/cloud.svg" --output cloud.svg
```

### `appliances`

```text
usage: gns3lab appliances [-h] [--filter FILTER] [--json]
```

Catálogo de appliances (`GET /v2/appliances`), filtrable por nombre, categoría, fabricante o
descripción. Las coincidencias por nombre salen primero.

```bash
gns3lab appliances --filter pfsense
```

### `disk`

```text
usage: gns3lab disk [-h] [--set SET] [--yes] [--json] {binaries,config}
```

`binaries` lista los binarios de `qemu-img` del compute. `config --set clave=valor --yes`
cambia su configuración.

```bash
gns3lab disk binaries
gns3lab disk config --set qemu_img=/usr/bin/qemu-img --yes
```

### `vm`

```text
usage: gns3lab vm [-h] [--engine {virtualbox,vmware}] [--set SET] [--yes]
                  [--json]
                  {vms,vmnet}
```

`vms` lista VMs invitadas de VirtualBox y VMware. `vmnet --set clave=valor --yes` crea una
interfaz vmnet en VMware. Sin VirtualBox/VMware la API responde 409 y la CLI muestra el mensaje
literal.

```bash
gns3lab vm vms --engine virtualbox
```

### `gns3vm`

```text
usage: gns3lab gns3vm [-h] [--set SET] [--json]
                      {show,set,engines,vms} [engine]
```

Lee o configura la GNS3 VM remota y sus motores. `set` relee para verificar que la API aplicó
los campos.

```bash
gns3lab gns3vm show
gns3lab gns3vm engines
gns3lab gns3vm vms vmware
```

### `iou-license`

```text
usage: gns3lab iou-license [-h] [--license LICENSE] [--json] [--yes] {get,set}
```

`get` lee la licencia IOU; `set --license LLAVE --yes` la cambia y la relee. La llave no se
escribe en el repo.

```bash
gns3lab iou-license get
```

### `server`

```text
usage: gns3lab server [-h] [--yes] {shutdown,reload,debug}
```

`shutdown`, `reload` y `debug` exigen `--yes` o TTY. Acepta `502`/`503`/`504` como respuesta
válida: tras un apagado el socket puede cerrarse antes del `200`.

```bash
gns3lab server reload --yes
```

### `notify` / `watch`

```text
usage: gns3lab notify [-h] [--count COUNT] [--json] [project]
usage: gns3lab watch [-h] [--project PROJECT] [--seconds SECONDS] [--json]
```

`notify` lee una ventana acotada del stream HTTP (`--count`, 10 por defecto) para no colgarse.
`watch` abre el WebSocket con la stdlib y sale por timeout (`--seconds`).

```bash
gns3lab notify examen-kit --count 3
gns3lab watch --project examen-kit --seconds 5
```

## Topología

### `node`

```text
usage: gns3lab node [-h] [-p PROJECT] [--size SIZE] [--proposals] [--json]
                    [--template TEMPLATE] [--name NAME] [--set SET]
                    [--port PORT] [--from-disk FROM_DISK] [--wait WAIT] [-x X]
                    [-y Y]
                    {add,rm,dup,props,switch,disk,disk-resize,links,idlepc,
                    start,stop,reload,suspend,resume,pause,unpause,line}
                    [node]
```

| Acción | Uso |
|---|---|
| `add --template T` | instancia una plantilla; manda `compute_id: local` |
| `rm` | borra el nodo |
| `dup --name N` | duplica el nodo |
| `props --set k=v` | edita propiedades; los campos del nodo se separan de `properties` |
| `switch --port N=tipo[:vlan]` | reescribe `ports_mapping`; cada entrada lleva `port_number` |
| `disk --from-disk F --name N` | clona un qcow2 local y apunta el nodo al clon |
| `disk-resize --size GB` | redimensiona el disco |
| `links` | enlaces del nodo |
| `idlepc [--proposals]` | idlepc de Dynamips |
| `start|stop|reload|suspend|resume|pause|unpause` | acción sobre un nodo; `--wait` segundos |
| `line` | línea de comandos real del proceso |

```bash
gns3lab node add --template "pfSense 2.7.2 (VNC)" --name PF1 -p examen-kit -x -250 -y -120
gns3lab node props PF1 -p examen-kit --set adapter_type=e1000 --set linked_clone=false
gns3lab node switch SW1 -p examen-kit --port 0=dot1q:43 --port 1=access:20
gns3lab node disk-resize PF1 --size 20 -p examen-kit
gns3lab node links PF1 -p examen-kit
gns3lab node start PF1 --wait 60 -p examen-kit
```

`props --set console=5902` no cambia el puerto: la API devuelve 200 y lo ignora; se fija en la
plantilla.

### `link`

```text
usage: gns3lab link [-h] [-p PROJECT] [--json] [--set SET] [--pa PA] [--pb PB]
                    [--ppa PPA] [--ppb PPB]
                    {list,add,rm,edit,filters} [nodes ...]
```

| Acción | Uso |
|---|---|
| `list` | id corto y extremos `A:a/p <-> B:a/p` |
| `add A B` | crea el enlace; `--pa/--pb` adaptador, `--ppa/--ppb` puerto |
| `rm <link_id>` | borra |
| `edit <link_id> --set k=v` | actualiza y **relee** para comprobar |
| `filters <link_id>` | filtros disponibles |

```bash
gns3lab link list -p examen-kit
gns3lab link add PF1 SW1 --pa 1 --pb 0 --ppb 0 -p examen-kit
gns3lab link filters 1a2b3c4d -p examen-kit
```

En un switch, `--pb` es el adaptador (0) y `--ppb` el puerto (Ethernet1 = `--ppb 1`).

### `draw`

```text
usage: gns3lab draw [-h] [--set SET] [-p PROJECT] [-x X] [-y Y]
                    [--color COLOR]
                    text [text ...]
```

Crea una nota SVG. `list` las lista, `edit <id> --set k=v` edita (`x`, `y`, `z`, `rotation`,
`locked`, `svg`) y `rm <id>` borra. `edit` relee el dibujo.

```bash
gns3lab draw "192.168.10.0/24 -> OPT1" -p examen-kit -x -200 -y 120
gns3lab draw list -p examen-kit
gns3lab draw edit 1a2b3c4d --set x=0 -p examen-kit
gns3lab draw rm 1a2b3c4d -p examen-kit
```

### `snap`

```text
usage: gns3lab snap [-h] {list,create,restore,delete} [name] [project]
```

`create` y `restore` paran los nodos arrancados, ejecutan y vuelven a arrancarlos.

```bash
gns3lab snap create antes-de-tocar examen-kit
gns3lab snap list "" examen-kit
gns3lab snap restore antes-de-tocar examen-kit
gns3lab snap delete antes-de-tocar examen-kit
```

El segundo posicional es el **nombre**, no el proyecto: `snap list examen-kit` lo interpreta
como nombre de snapshot. Para listar un proyecto concreto, pasa `"" examen-kit`.

### `all`

```text
usage: gns3lab all [-h] [-p PROJECT] [--yes] [--json]
                   {start,stop,suspend,reload}
```

Acción masiva sobre todos los nodos del proyecto. Exige `--yes` o confirmación en TTY.

```bash
gns3lab all stop -p examen-kit --yes
```

### `nio`

```text
usage: gns3lab nio [-h] --adapter ADAPTER --port PORT [--nio NIO]
                   [--emulator EMULATOR] [-p PROJECT] [--json]
                   {get,add,rm} node
```

NIO de un puerto del compute local. `get` lee, `add --nio JSON` hace `PUT` y `rm` borra. El
`PUT` sólo aplica `filters` y `suspend`; crear un NIO UDP nuevo es un `POST` que la CLI no
expone.

```bash
gns3lab nio get PC1 --adapter 0 --port 0 -p examen-kit
gns3lab nio add PC1 --adapter 0 --port 0 \
  --nio '{"type":"nio_udp","lport":10000,"rhost":"127.0.0.1","rport":20000}' -p examen-kit
gns3lab nio rm PC1 --adapter 0 --port 0 -p examen-kit
```

### `capture-port`

```text
usage: gns3lab capture-port [-h] --adapter ADAPTER --port PORT [--file FILE]
                            [--emulator EMULATOR] [-p PROJECT] [--json]
                            node {start,stop,pcap}
```

Captura en un puerto del compute, no en un enlace. `pcap` guarda el fichero en
`~/GNS3/captures/`.

```bash
gns3lab capture-port PC1 start --adapter 0 --port 0 -p examen-kit
gns3lab capture-port PC1 stop --adapter 0 --port 0 -p examen-kit
gns3lab capture-port PC1 pcap --adapter 0 --port 0 -p examen-kit
```

### `capture`

```text
usage: gns3lab capture [-h] [-p PROJECT] link {start,stop,pcap}
```

Captura de un **enlace** del controlador. `pcap` descarga el fichero; si la captura sigue
activa, la API no responde hasta pararla y la CLI usa el `.pcap` del proyecto.

```bash
gns3lab capture 1a2b3c4d start -p examen-kit
gns3lab capture 1a2b3c4d stop -p examen-kit
gns3lab capture 1a2b3c4d pcap -p examen-kit
```

## Consola y pantalla

### `exec`

```text
usage: gns3lab exec [-h] [-p PROJECT] [--expect EXPECT] [--idle IDLE]
                    [--timeout TIMEOUT] [--ready-timeout READY_TIMEOUT]
                    [--answer ANSWERS]
                    node commands [commands ...]
```

Consola telnet leída por prompt o quietud. Responde solo a `--More--`, `[y/n]` y `Password:`.
La cabecera con el prompt va a `stderr`; cada comando va precedido de `$` en `stdout`.

```bash
gns3lab exec PC1 "ip dhcp" "show ip" -p examen-kit
gns3lab exec Router1 "show ip route" --expect '# $' -p examen-kit
```

Sólo para nodos con `console_type` telnet. En pfSense (VNC) remite al monitor QEMU.

### `console`

```text
usage: gns3lab console [-h] [-p PROJECT] [--send SEND] [--expect EXPECT]
                       [--idle IDLE] [--timeout TIMEOUT]
                       [--ready-timeout READY_TIMEOUT] [--yes]
                       node [target]
```

Una sola sesión telnet. Sin `--send` es interactiva por stdin; `exit` o Ctrl-D sale sin enviar
nada. `console reset <nodo>` reinicia el proxy, `console url <nodo>` da la URL WebSocket y
`console reset-all --yes` reinicia todas las consolas del proyecto.

```bash
gns3lab console PC1 -p examen-kit
gns3lab console PC1 --send "show ip" -p examen-kit
gns3lab console reset PF1 -p examen-kit
gns3lab console reset-all -p examen-kit --yes
```

### `shot`

```text
usage: gns3lab shot [-h] [-p PROJECT] [--psm PSM] [--scale SCALE] [--no-ocr]
                    node
```

`gns3lab shot` captura el framebuffer real por HMP, lo convierte a PNG y lo pasa por OCR.
Por defecto `--psm 4` y `--scale 2`.

```bash
gns3lab shot PF1 -p examen-kit
```

Confirma la ruta `~/GNS3/captures/screen-...png`, su tamaño y el texto. Mira el **final** del
texto: el arranque deja logs intercalados. Sólo funciona con el nodo arrancado en el compute
local.

### `key` / `type`

```text
usage: gns3lab key [-h] [-p PROJECT] [--delay DELAY] [--show]
                   node keys [keys ...]
usage: gns3lab type [-h] [-p PROJECT] [--enter] [--delay DELAY] [--psm PSM]
                    [--no-show]
                    node text
```

`key` usa nombres HMP (`ret`, `down`, `shift-2`, `f2`). `type` traduce carácter a tecla y manda
`sendkey shift` antes para despertar la consola del invitado.

```bash
gns3lab key PF1 ret -p examen-kit
gns3lab key PF1 down down ret --show -p examen-kit
gns3lab type PF1 "2" --enter -p examen-kit
```

Enter es `ret`, no `enter`. Antes de aceptar una opción, comprueba con `shot` que el eco está en
pantalla: un `ret` con la línea vacía sólo redibuja el menú.

### `mon`

```text
usage: gns3lab mon [-h] [-p PROJECT] node cmd [cmd ...]
```

Comando HMP crudo. Devuelve JSON con `cmd`, `output`, `error` y `raw_len`. `system_reset`
reinicia la VM: es un cambio de estado.

```bash
gns3lab mon PF1 info status -p examen-kit
```

## pfSense

Todos los subcomandos aceptan `--json` y devuelven `{ok, data}`. `detect` no usa SSH; el resto
lee `PFSENSE_HOST`, `PFSENSE_PORT`, `PFSENSE_USER` y `PFSENSE_PASSWORD` del entorno.

```text
usage: gns3lab pf [-h] {detect,status,config,assign,ip,dhcp,rule,nat,ssh} ...
```

```bash
gns3lab pf detect -p examen-kit
gns3lab pf status
gns3lab pf config get > fw.xml
gns3lab pf config put fw.xml --yes
gns3lab pf assign --wan em0 --lan em1
gns3lab pf ip em1 192.168.1.1 24
gns3lab pf dhcp em1 192.168.1.100 192.168.1.200
gns3lab pf rule pass --if lan --proto tcp --src any --dst any --port 80
gns3lab pf nat --if wan
gns3lab pf ssh --port 22022
```

`rule` y `nat` insertan antes de cualquier `reject`. `put_config` hace copia de seguridad
`config.xml.bak-<stamp>`, recarga con `/etc/rc.reload_all` y no borra secciones que no entiende.
Detalle en [PFSENSE-NATIVO.md](PFSENSE-NATIVO.md).

## Ficheros y discos

### `upload`

```text
usage: gns3lab upload [-h] [--name NAME] [--no-compress] file
```

Sube un disco o ISO al compute local. Un `.qcow2` se comprime con `qemu-img convert -c` salvo
`--no-compress`; al final verifica que aparece en la lista de imágenes.

```bash
gns3lab upload ~/GNS3/images/QEMU/pfSense.qcow2 --name pfSense-examen.qcow2
```

Confirma `OK: ... verificado (N imágenes en el servidor)`. Si no aparece, sale con código 1.

Matriz endpoint a endpoint en [API-COVERAGE.md](API-COVERAGE.md); paridad con el MCP en
[PARIDAD.md](PARIDAD.md); guion del examen en [EXAMEN.md](EXAMEN.md).
