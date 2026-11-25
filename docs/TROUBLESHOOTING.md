# Troubleshooting

Síntoma literal, causa y arreglo. Las trampas marcadas con «pagada» ya costaron tiempo en el
montaje real; están en `AGENTS.md` y no se repiten.

| Síntoma | Causa | Arreglo |
|---|---|---|
| `servidor local (http://127.0.0.1:3080) no responde` o `no puedo conectar con ...` | `gns3server` parado, o no hay red hacia el aula | arranca el servidor y comprueba con `gns3lab servers`; para el aula, `ping 192.168.71.250` |
| `The image X is missing` | el `.gns3p` no lleva los discos | `gns3lab upload <disco> --name X` o repunta el nodo a un `empty*.qcow2` e instala desde el ISO |
| `... can only be used once on your server` | dos nodos comparten el mismo qcow2 sin `linked_clone` | `gns3lab node props NODO --set linked_clone=true`, o clona: `gns3lab node disk NODO --name otro.qcow2` |
| `NAT interface virbr1 is missing` | `libvirtd` parado; las redes `gns3-nat*` no existen | `sudo systemctl start libvirtd`; `gns3lab doctor` lo detecta como `libvirtd parado` |
| pfSense repite «interface mismatch» en bucle | el disco trae `em0/em1` y el nodo arranca con `virtio-net-pci` | `gns3lab node props PF1 --set adapter_type=e1000` y vuelve a arrancar |
| `Port 1/0 for SW1 not found` | pasaste el puerto del switch como adaptador | el adaptador del switch es 0 y el puerto va en `--ppb`: `link add PF1 SW1 --pb 0 --ppb 1` |
| `docker.io/... not found` al abrir un proyecto importado | tag de imagen viejo (`chromium:dhcp`) | `import` lo cambia si el destino tiene otra etiqueta de la misma imagen; a mano, mira `gns3lab templates` y `node props NODO --set image=<imagen del destino>` |
| El PNG de `screendump` no abre | **trampa pagada**: `screendump` escribe un **PPM** con extensión `.png` | usa `gns3lab shot`, que convierte y borra el PPM; a mano, `magick ppm:screen.png png:screen-real.png` |
| El OCR lee `Shou` donde pone `Show` | **trampa pagada**: la fuente VGA confunde `w` con `u` a escala 1 | `gns3lab shot` usa escala 2 y `psm 4`; el núcleo corrige `Shou`/`shou`. Revisa el texto antes de fiarte |
| Pulsar Enter no hace nada o QEMU rechaza la tecla | **trampa pagada**: HMP llama `ret` a Enter, no `enter` | `gns3lab key PF1 ret`; mayúsculas y símbolos con `shift-<tecla>` |
| La primera tecla no aparece y el menú sigue igual | **trampa pagada**: la consola del invitado duerme y se come la primera tecla | `gns3lab type` ya manda `sendkey shift`; con `key`, mándalo tú: `gns3lab key PF1 shift down ret` |
| El Enter acepta la opción por defecto | tecleaste sin eco y el `ret` llegó con la línea vacía | comprueba con `shot` **antes** del `--enter`; si no está el carácter, repite `type` |
| `404` al añadir un nodo desde una plantilla | **trampa pagada**: falta `compute_id: local` en el body | la CLI y el MCP ya lo mandan; si llamas a la API a mano, inclúyelo |
| `JSON schema error` al cambiar `ports_mapping` | **trampa pagada**: `port_number` es obligatorio en todas las entradas | `gns3lab node switch` lo rellena; si vas por API, no omitas `port_number` en ningún puerto |
| `startup.vpc` con JSON dentro y VPCS no lo ejecuta | **trampa pagada**: `POST /nodes/{id}/files/{ruta}` graba el body **en crudo** | manda el texto plano, no `{"content": ...}`; usa `gns3_node_files` o `node_file_write`, que mandan el texto plano |
| `409 Project must be stopped` al crear snapshot o exportar | GNS3 exige el proyecto parado | `gns3lab snap create` y `gns3lab port` paran y re-arrancan solos; a mano, `gns3lab down PROY --keep-open` antes |
| `gns3lab node props ... --set console=5902` no cambia el puerto | **trampa pagada**: el puerto de consola no se fija por `PUT` | fíjalo en la plantilla antes de crear el nodo |
| `no encuentro el monitor del nodo QEMU` | el nodo no está arrancado, o el proceso es de otro usuario/servidor | arranca con `gns3lab up`; `shot`/`key` sólo ven `/proc` del compute local |
| `sin traducción a tecla: [...]` | el texto tiene un carácter que `key_for` no sabe mapear | escribe sólo ASCII imprimible; para el resto, `key` con el nombre HMP |
| La pantalla sale en blanco o a medias | capturaste durante el arranque | espera y repite `shot`; mira el final del texto, no el principio |
| `test` dice `gateway=255.255.255.0` | VPCS pinta la máscara en el campo gateway tras `ip dhcp` | el arreglo lo aplica `test`: usa el `DHCP SERVER` de `show ip` como gateway y reconfigura la IP |
| `gateway=... y sin concesión DHCP; revisa pfSense` | el DHCP del firewall no responde o la VLAN no está bien | revisa `node switch`, la asignación de OPT y que la regla `easyrule pass opt1 ...` exista |
| `ninguno abierto; di cuál: ...` | hay varios proyectos y ninguno abierto | pasa el nombre: `gns3lab status examen`; o abre uno con `up` |
| `'x' es ambiguo: ...` | el nombre parcial casa con varios proyectos | usa el prefijo del `project_id` que imprime `gns3lab status` |
| `snap list examen` no lista el proyecto `examen` | el segundo posicional de `snap` es el nombre del snapshot | `gns3lab snap list "" examen` |
| `origen y destino son el mismo servidor` | `port` con `--from` igual al destino | elige otro `-s` o cambia `--from` |
| `OK: X NO aparece en la lista (N imágenes en el servidor)` tras `upload` | la subida devolvió 2xx pero el compute no ve la imagen | repite `gns3lab images`; si sigue, revisa espacio y permisos en el servidor |
| `doctor` avisa `sin tesseract` | falta el binario | instálalo (`tesseract`); sin él `shot` devuelve imagen y texto vacío, no falla |
| `doctor` avisa `sin Pillow: el screendump queda en PPM` | no hay Pillow ni ImageMagick | instala `python-pillow` o `imagemagick`; el PNG real lo necesitas para el OCR |
| `doctor` avisa `disco compartido X entre [...]` | dos nodos con la misma imagen y distinta config | `gns3lab node disk NODO --name exclusivo.qcow2` |
| `doctor` avisa `sin monitor HMP visible` | el QEMU corre con otro usuario o en otro equipo | en el aula, usa consola telnet o VNC; `shot`/`key` no llegarán |
| Un nodo NAT no arranca y `node add` imprime la pista de libvirt | la red libvirt del NAT no está activa | `sudo systemctl start libvirtd` y repite; `doctor` lo lista |
| La WAN se queda sin IP y los PCs reciben «Destination host unreachable» del firewall | no hay nodo NAT ni salida | `gns3lab node add --template NAT --name NAT1` y enlázalo; `import`/`port` lo añaden si falta |
