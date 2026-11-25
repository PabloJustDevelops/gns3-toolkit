# Comandos de `gns3lab`

Referencia de los subcomandos que registra el parser (`cli/gns3lab`, `main()`), con las flags
tal como aparecen en `gns3lab <cmd> --help`. Los ejemplos usan el proyecto `examen` y suponen
el servidor local; para el del aula se pone `-s clase` **antes** del subcomando.

**Convenciones comunes**

- `--server`, `-s`: servidor configurado. Global, va antes del subcomando. Por defecto, el
  `default_server` de `~/.config/gns3lab/config.json` (se crea con `local` y `clase` la primera
  vez que se ejecuta la CLI).
- El proyecto se identifica por nombre parcial o por prefijo del `project_id`. Si se omite: el
  único abierto; si no hay ninguno abierto, el único que exista. En el servidor de aula, si hay
  varios abiertos, la config puede traer un `matcher` (por ejemplo `Pablo Rodriguez`) para
  desempatar.
- `-p`, `--project` lo llevan `exec`, `shot`, `key`, `type`, `mon`, `node`, `draw` y `link`. El
  resto lo recibe como posicional.
- Códigos de salida: `0` correcto, `1` algún fallo (nodo, enlace, comprobación), `2` servidor
  que no responde en `status` y `doctor`.
- Credenciales: sólo el servidor `local` las lee de `~/.config/GNS3/2.2/gns3_server.conf`. No se
  escriben en el repo ni en el prompt.

## servers

Lista los servidores de la config, si responden, su versión, cuántos proyectos tienen y si usan
autenticación.

```text
usage: gns3lab servers [-h]
```

```bash
gns3lab servers
```

Confirma: una línea `[OK ]` por servidor alcanzable, con `v2.2.61, N proyecto(s), auth=sí`.
`[NO ]` con la línea vacía al final significa que ese servidor no contesta.

## status

Lista los proyectos, marca con `*` el que se seleccionaría y, para ese, pinta sus nodos con
tipo, estado y puerto de consola.

```text
usage: gns3lab status [-h] [project]
```

| Argumento | Qué es |
|---|---|
| `project` | nombre o id del proyecto (opcional) |

```bash
gns3lab status examen
```

Confirma: `* examen ... abierto` y debajo una línea por nodo con `started` y `telnet:<puerto>`
o `vnc:<puerto>`. Si el servidor no responde, sale con código 2.

## up

Abre el proyecto si está cerrado y arranca los nodos que no estén `started`. Espera 3 s y
vuelve a leer el estado.

```text
usage: gns3lab up [-h] [project]
```

```bash
gns3lab up examen
```

Confirma: la cabecera `examen: N nodos, arranco N` y, al final, cada nodo con `started`. Sale
con código 1 si algún `start` devolvió error.

## down

Para los nodos arrancados y cierra el proyecto, salvo `--keep-open`.

```text
usage: gns3lab down [-h] [--keep-open] [project]
```

| Flag | Efecto |
|---|---|
| `--keep-open` | para los nodos pero no cierra el proyecto |

```bash
gns3lab down examen --keep-open
```

Confirma: `examen: parado (N nodos), proyecto sigue abierto`; sin la flag, `parado y cerrado`.

## test

Conectividad real por las consolas telnet de los nodos VPCS: lee IP y gateway, corrige la
gateway cuando VPCS pinta la máscara, y hace ping entre PCs, a la gateway y a `8.8.8.8`.

```text
usage: gns3lab test [-h] [project]
```

```bash
gns3lab test examen
```

Confirma: bloques `gateway` y `conectividad` con líneas `OK` y ninguna `FALLO`. Si dice que la
gateway es `255.255.255.0`, es el cliente VPCS: el dato bueno es el campo `DHCP SERVER` de
`show ip`, que es el que usa el arreglo.

## export

Descarga el proyecto como `.gns3p` (zip). Exige que el proyecto se pueda exportar; el fichero
debe empezar por `PK`.

```text
usage: gns3lab export [-h] dest [project]
```

| Argumento | Qué es |
|---|---|
| `dest` | ruta del `.gns3p` a escribir |
| `project` | proyecto de origen (opcional) |

```bash
gns3lab export ~/GNS3/exports/examen.gns3p examen
```

Confirma: `guardado /home/.../examen.gns3p (N KB)`. El export no lleva las imágenes de disco.

## import

Importa un `.gns3p` corrigiéndolo antes de subirlo: quita los nodos `cloud`, activa
`linked_clone`, cambia discos que no existen en el destino por un `empty*.qcow2` si lo hay,
arregla tags de Docker, añade un NAT si no hay salida y pasa los `startup.vpc` a `ip dhcp`.
Después lo abre.

```text
usage: gns3lab import [-h] file [name]
```

| Argumento | Qué es |
|---|---|
| `file` | `.gns3p` de origen |
| `name` | nombre en el destino (opcional) |

```bash
gns3lab import ~/GNS3/exports/examen.gns3p examen-copia
```

Confirma: `correcciones antes de subir:` con la lista, `importado (N KB) como id xxxxxxxx`,
`renombrado a 'examen-copia' [200]` y `abierto: N nodos, N enlaces`. Existe una flag oculta
`--no-rename` que el código ignora.

## fix

Repara un proyecto ya importado que no abre. Exporta, reescribe el `.gns3` en disco, reimporta
con id nuevo y, salvo `--keep-both`, borra el roto y devuelve el nombre original.

```text
usage: gns3lab fix [-h] [--keep-both] [project]
```

| Flag | Efecto |
|---|---|
| `--keep-both` | no borra el proyecto roto |

```bash
gns3lab fix examen
```

Confirma: `no había nada que corregir` o la lista de cambios seguida de `reparado como examen
(xxxxxxxx)`. No hace las correcciones de WAN ni de `startup.vpc` que sí aplica `import`.

## port

Porta un proyecto de un servidor a otro: para los nodos del origen, exporta, sube los discos que
falten (comprimidos con `qemu-img convert -c` si son qcow2), aplica las correcciones de `import`,
importa, renombra y, con `--start`, arranca.

```text
usage: gns3lab port [-h] [--from FROM_SERVER] [--name NAME] [--start]
                    [--no-compress]
                    [project]
```

| Flag | Efecto |
|---|---|
| `--from` | servidor de origen (por defecto `local`) |
| `--name` | nombre del proyecto en el destino |
| `--start` | arranca los nodos al terminar |
| `--no-compress` | sube el qcow2 tal cual |

```bash
gns3lab -s clase port examen --from local --name "Pablo Rodriguez" --start
```

Confirma: `origen : local — examen (xxxxxxxx)`, `destino: clase — http://...`, el tamaño del
export, `discos que faltan en el destino: ...` con `OK` por cada subida, `correcciones:`,
`importado como 'Pablo Rodriguez' (xxxxxxxx)` y `abierto: N nodos, N enlaces`. Si el destino es
el mismo servidor, aborta. Los discos se suben al compute local del destino.

## images

Lista los nombres de las imágenes QEMU del compute local.

```text
usage: gns3lab images [-h]
```

```bash
gns3lab images
```

Confirma: una imagen por línea (`empty10G.qcow2`, `openwrt-...qcow2`, ISOs). Lista vacía suele
significar que el compute no responde, no que no haya imágenes.

## templates

Lista las plantillas del servidor con su tipo y nombre. Es de donde salen los valores de
`--template` en `node add`.

```text
usage: gns3lab templates [-h]
```

```bash
gns3lab templates
```

Confirma: líneas `qemu pfSense 2.7.2 (VNC)`, `nat NAT`, `ethernet_switch Ethernet switch`,
`vpcs VPCS`, etc.

## snap

Snapshots del proyecto. `create` y `restore` paran los nodos arrancados, ejecutan la operación y
vuelven a arrancarlos.

```text
usage: gns3lab snap [-h] {list,create,restore} [name] [project]
```

| Acción | Uso |
|---|---|
| `list` | lista nombres de snapshot |
| `create <nombre>` | crea el snapshot |
| `restore <nombre>` | restaura ese snapshot |

```bash
gns3lab snap create antes-de-tocar examen
gns3lab snap list "" examen
gns3lab snap restore antes-de-tocar examen
```

Confirma: `crear 'antes-de-tocar' -> [200]`, la lista con el nombre, y `restaurar ... -> [200]`.

Aviso de sintaxis: el segundo posicional es el **nombre**, no el proyecto. `snap list examen`
interpreta `examen` como nombre de snapshot e ignora el proyecto; para listar uno concreto hay
que pasar `"" examen`, como en el ejemplo.

## exec

Ejecuta comandos en la consola **telnet** del nodo. Lee por prompt o por quietud, responde solo a
`--More--`, a `[y/n]` y a `Password:`, y devuelve la salida de cada comando por separado. La
cabecera con el prompt detectado va a stderr.

```text
usage: gns3lab exec [-h] [-p PROJECT] [--expect EXPECT] [--idle IDLE]
                    [--timeout TIMEOUT] [--ready-timeout READY_TIMEOUT]
                    [--answer ANSWERS]
                    node commands [commands ...]
```

| Flag | Efecto |
|---|---|
| `-p, --project` | proyecto |
| `--expect` | regex que cierra la lectura (por ejemplo `'\$ $'`) |
| `--idle` | segundos de quietud por comando (0.9) |
| `--timeout` | máximo por comando en segundos (20) |
| `--ready-timeout` | espera a que el nodo dé prompt (30) |
| `--answer` | respuesta a `[y/n]`, repetible |

```bash
gns3lab exec PC1 "ip dhcp" "show ip" -p examen
gns3lab exec Router1 "show ip route" --expect '# $' -p examen
```

Confirma: en stderr `examen / PC1  prompt='...' ready=True` y en stdout cada comando precedido
de `$`, con su salida. Un `[timeout tras N ms]` indica que la salida no se estabilizó. Sólo vale
para nodos con `console_type` telnet: en pfSense (VNC) remite al monitor QEMU.

## shot

Captura el framebuffer real del nodo QEMU por el monitor HMP, la guarda en PNG y la pasa por
OCR. Es la forma de leer un menú sin VNC.

```text
usage: gns3lab shot [-h] [-p PROJECT] [--psm PSM] [--scale SCALE] [--no-ocr]
                    node
```

| Flag | Efecto |
|---|---|
| `-p, --project` | proyecto |
| `--psm` | modo de página de tesseract (4) |
| `--scale` | reescala antes del OCR (2) |
| `--no-ocr` | sólo el PNG, sin texto |

```bash
gns3lab shot PF1 -p examen
```

Confirma: la ruta `~/GNS3/captures/screen-AAAAmmdd-HHMMSS.png`, su tamaño, y el texto de la
pantalla. Mira el **final** del texto: el arranque deja logs intercalados. Busca el nodo con
`/proc` (por eso sólo funciona con el compute local y el nodo arrancado).

## key

Pulsa teclas por el monitor HMP del nodo QEMU, con nombres de QEMU: `ret`, `down`, `up`,
`shift-2`, `f2`.

```text
usage: gns3lab key [-h] [-p PROJECT] [--delay DELAY] [--show]
                   node keys [keys ...]
```

| Flag | Efecto |
|---|---|
| `-p, --project` | proyecto |
| `--delay` | pausa entre teclas (0.08 s) |
| `--show` | OCR de la pantalla al terminar |

```bash
gns3lab key PF1 shift ret -p examen
gns3lab key PF1 down down ret --show -p examen
```

Confirma: sin salida si no se pide `--show`; con `--show`, el texto de la pantalla ya
actualizado. Enter es `ret`, no `enter`.

## type

Escribe un texto traduciendo cada carácter a `sendkey`. Antes manda un `sendkey shift` para
despertar la consola del invitado, que se come la primera tecla si lleva rato dormida.

```text
usage: gns3lab type [-h] [-p PROJECT] [--enter] [--delay DELAY] [--psm PSM]
                    [--no-show]
                    node text
```

| Flag | Efecto |
|---|---|
| `-p, --project` | proyecto |
| `--enter` | pulsa Enter al terminar |
| `--delay` | pausa entre teclas (0.08 s) |
| `--psm` | modo de página del OCR final (4) |
| `--no-show` | no hace OCR después |

```bash
gns3lab type PF1 "2" --enter -p examen
```

Confirma: el OCR de la pantalla resultante, salvo `--no-show`. Si un carácter no tiene tecla,
avisa por stderr con `sin traducción a tecla`. Para aceptar una opción, comprueba antes con
`shot` que el eco está en pantalla: un Enter con la línea vacía sólo redibuja el menú.

## mon

Manda un comando HMP crudo al monitor y devuelve su respuesta como JSON.

```text
usage: gns3lab mon [-h] [-p PROJECT] node cmd [cmd ...]
```

```bash
gns3lab mon PF1 info status -p examen
gns3lab mon PF1 system_reset -p examen
```

Confirma: JSON con `cmd`, `output`, `error` y `raw_len`. `error` no nulo es el texto del propio
HMP. `system_reset` reinicia la VM: es un cambio de estado, no un diagnóstico.

## new

Crea un proyecto vacío y lo abre.

```text
usage: gns3lab new [-h] name
```

```bash
gns3lab new examen
```

Confirma: `examen creado (xxxxxxxx), abierto=True`. El `path` que manda es
`$HOME/GNS3/projects/<nombre>` de tu usuario: en un servidor remoto con otro usuario esa ruta
puede no existir.

## node

Operaciones sobre nodos: `add`, `rm`, `dup`, `props`, `switch`, `disk`.

```text
usage: gns3lab node [-h] [-p PROJECT] [--template TEMPLATE] [--name NAME]
                    [--set SET] [--port PORT] [--from-disk FROM_DISK] [-x X]
                    [-y Y]
                    {add,rm,dup,props,switch,disk} [node]
```

| Flag | Uso |
|---|---|
| `-p, --project` | proyecto |
| `--template` | `add`: nombre o id de plantilla |
| `--name` | nombre nuevo en `dup`, `add` y `disk` |
| `--set` | `props`: `clave=valor`, repetible |
| `--port` | `switch`: `N=tipo[:vlan]`, repetible |
| `--from-disk` | `disk`: qcow2 de origen |
| `-x`, `-y` | posición en el canvas |

```bash
gns3lab node add --template "pfSense 2.7.2 (VNC)" --name PF1 -p examen -x -250 -y -120
gns3lab node props PF1 -p examen --set adapter_type=e1000 --set linked_clone=false
gns3lab node switch SW1 -p examen --port 0=dot1q:43 --port 1=access:20 --port 2=access:30
gns3lab node dup PC1 --name PC2 -p examen -x 300 -y -300
gns3lab node disk PF1 --name pfSense-pf1.qcow2 -p examen
gns3lab node rm PC2 -p examen
```

Confirma: `add` imprime `PF1 (xxxxxxxx) tipo=qemu`; `props`, `PF1: {...} -> OK`; `switch`,
`SW1: N puertos -> OK`; `dup`, `duplicado como PC2 (xxxxxxxx)`; `disk`, `... enlazado=True`;
`rm`, `PC2 borrado=True`.

Detalles que importan:

- `add` manda `compute_id: local` en el body; sin él la API devuelve 404.
- `props` separa los campos del nodo (`name`, `console`, `console_type`, `x`, `y`, `z`,
  `symbol`, `locked`) de los de `properties`; los valores se intentan leer como JSON y, si no,
  como texto. `console` por `PUT` no cambia el puerto: se fija en la plantilla.
- `switch` reescribe `ports_mapping` completo; cada entrada lleva `port_number`.
- `disk` clona en `~/GNS3/images/QEMU` con `qemu-img convert` (o `cp` si falta) y apunta el nodo
  al clon con `linked_clone: false`. Es una operación local.

## upload

Sube un disco o ISO al compute local del servidor. Un `.qcow2` se comprime con
`qemu-img convert -c` salvo `--no-compress`. Verifica al final que el nombre aparece en la lista
de imágenes.

```text
usage: gns3lab upload [-h] [--name NAME] [--no-compress] file
```

| Flag | Efecto |
|---|---|
| `--name` | nombre en el servidor (por defecto, el del fichero) |
| `--no-compress` | no comprimir el qcow2 |

```bash
gns3lab upload ~/GNS3/images/QEMU/pfSense.qcow2 --name pfSense-examen.qcow2
```

Confirma: `comprimiendo ...`, `-> N MB`, `subiendo ...`, y `OK: pfSense-examen.qcow2
verificado (N imágenes en el servidor)`. Si dice `NO aparece en la lista`, sale con código 1.

## draw

Crea una nota de texto en el canvas del proyecto (un SVG con un rectángulo y el texto). Sirve
para dejar el direccionamiento o las VLANs a la vista.

```text
usage: gns3lab draw [-h] [-p PROJECT] [-x X] [-y Y] [--color COLOR] text
```

| Flag | Efecto |
|---|---|
| `-p, --project` | proyecto |
| `-x`, `-y` | posición |
| `--color` | color del trazo y del texto (`#ffffff`) |

```bash
gns3lab draw "192.168.10.0/24 -> OPT1" -p examen -x -200 -y 120
```

Confirma: `nota creada`; si falla, imprime el cuerpo del error.

## link

Enlaces: `list`, `add <nodoA> <nodoB>`, `rm <link_id>`.

```text
usage: gns3lab link [-h] [-p PROJECT] [--pa PA] [--pb PB] [--ppa PPA]
                    [--ppb PPB]
                    {list,add,rm} [nodes ...]
```

| Flag | Efecto |
|---|---|
| `-p, --project` | proyecto |
| `--pa`, `--pb` | adaptador del primer y segundo nodo (0) |
| `--ppa`, `--ppb` | puerto del primer y segundo nodo (0) |

```bash
gns3lab link list -p examen
gns3lab link add PF1 NAT1 --pa 0 --pb 0 -p examen
gns3lab link add PC1 SW1 --pa 0 --pb 0 --ppb 1 -p examen
gns3lab link rm 1a2b3c4d -p examen
```

Confirma: `list` imprime `xxxxxxxx  PF1:0/0 <-> NAT1:0/0`; `add`, la misma línea con el
`link_id`; `rm`, `borrado=True`.

Confusión habitual: en un switch, `--pb` es el **adaptador** (0) y `--ppb` el **puerto**
(Ethernet1 = `--ppb 1`). Pasar `--pb 1` da `Port 1/0 for SW1 not found`.

## doctor

Chequeo integral antes de dar el lab por bueno: servidor y versión, computes conectados,
binarios (`tesseract`, `qemu-img`, `tshark`, `sshpass`), `libvirtd`, Pillow, proyecto y sus
nodos, monitor HMP visible, discos compartidos o ausentes y presencia de un nodo NAT.

```text
usage: gns3lab doctor [-h] [project]
```

```bash
gns3lab doctor examen
```

Confirma: bloque final `resumen` con `sin hallazgos` y código 0. Cualquier línea `- ...` es un
problema y el código es 1; si el servidor no responde, 2.

Salida real de un proyecto cerrado (los nodos aún sin arrancar):

```text
servidor local (http://127.0.0.1:3080)
  versión 2.2.61
  compute gigabyte-g5: conectado
  tesseract  OK
  qemu-img   OK
  tshark     OK
  sshpass    OK
  libvirtd   active
  Pillow     OK
  proyecto examen-kit (418e465b, closed)
    aviso: cerrado; `gns3lab up` lo abre
    PF1                qemu             -         console=5901 (vnc)
    ...
  resumen
    - PF1 no está arrancado
```
