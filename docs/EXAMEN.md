# Guion del examen

Secciones: Atajo: el kit en tres comandos · 1. Comprobar el servidor · 2. Levantar el kit · 3. Leer el menú de pfSense por OCR · 4. Asignar interfaces · 5. VLANs en el switch · 6. Verificar con ping y doctor · 7. Llevarlo al servidor del aula · Lista final.

Secuencia para montar y entregar el escenario sin GUI, en el orden en que se hace. Cada paso
lleva el comando exacto y la salida que confirma que salió bien. Si un paso no imprime lo que
pone aquí, no sigas: está en [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

Referencia de flags: [COMANDOS.md](COMANDOS.md). El proyecto se llama `examen` en todo el guion.

## Atajo: el kit en tres comandos

`gns3lab` trae el montaje automatizado. Cambia estado del servidor, así que se reporta:

```bash
gns3lab examen setup --name "Kit de examen"    # crea proyecto, nodos y enlaces
gns3lab examen verify --name "Kit de examen"   # estado, enlaces y ping real
gns3lab examen informe --name "Kit de examen"  # Markdown en ~/GNS3/informes/
```

Si el kit ya está montado a mano, el guion de abajo sigue siendo la referencia de qué se
comprueba y qué salida confirma cada paso.

## 1. Comprobar el servidor

```bash
gns3lab servers
```

Confirma:

```text
  [OK ] local    http://127.0.0.1:3080            v2.2.61, 6 proyecto(s), auth=sí
  [NO ] clase    http://192.168.71.250:80
```

`[NO ]` en `local` es que el servidor no está arrancado; en `clase`, que no hay red hacia el
aula. Sin `[OK ]` no hay nada más que hacer.

```bash
gns3lab doctor
```

Confirma: `compute ...: conectado`, `libvirtd active` y `Pillow OK`. Si `libvirtd` está parado,
los nodos NAT no se crean: `sudo systemctl start libvirtd`.

## 2. Levantar el kit

```bash
gns3lab status examen-kit
gns3lab up examen-kit
gns3lab status examen-kit
```

Confirma, en el segundo `status`, cada nodo con `started` y su consola (`telnet:5011`,
`vnc:5901`). `up` imprime `examen-kit: N nodos, arranco N` y la lista final de estados; código 0
es que todos los `start` fueron aceptados.

Antes de tocar nada, red de seguridad:

```bash
gns3lab snap create antes-examen examen-kit
```

Confirma: `crear 'antes-examen' -> [200]`. La CLI para y re-arranca los nodos sola.

## 3. Leer el menú de pfSense por OCR

```bash
gns3lab shot PF1 -p examen-kit
```

Confirma: una ruta `~/GNS3/captures/screen-...png`, su tamaño en KB y, debajo, el texto de la
pantalla. Tiene que aparecer el menú de pfSense con las opciones `1) Assign Interfaces`,
`2) Set interface(s) IP address`, `8) Shell`, etc.

Dos reglas de lectura:

- Mira el **final** del texto. Durante el arranque hay logs intercalados y el menú puede estar
  a media pintar.
- El OCR confunde `w` con `u` en algunas fuentes; el núcleo corrige `Shou`/`shou`, pero no
  confíes en una sola captura para leer un nombre de interfaz.

Si la captura falla con `no encuentro el monitor del nodo QEMU`, el nodo no está arrancado o su
proceso no es visible desde tu usuario. Vuelve al paso 2.

## 4. Asignar interfaces

Se hace a ciegas entre captura y captura. Primero la opción del menú:

```bash
gns3lab type PF1 "1" --enter -p examen-kit
gns3lab shot PF1 -p examen-kit
```

Confirma: la captura ya no muestra el menú, sino las preguntas de asignación (VLANs, WAN, LAN)
y el eco del `1`.

Responde a cada pregunta con los nombres que muestre la propia captura. En un pfSense con dos
adaptadores suele ser `em0`/`em1` o `vtnet0`/`vtnet1`, según el `adapter_type` del nodo. Por
ejemplo, si pide la WAN y el disco trae `em0`:

```bash
gns3lab type PF1 "em0" --enter -p examen-kit
gns3lab shot PF1 -p examen-kit
gns3lab type PF1 "em1" --enter -p examen-kit
gns3lab shot PF1 -p examen-kit
```

Confirma: la última captura muestra el resumen con `WAN (wan) -> em0` y `LAN (lan) -> em1`, y
vuelve al menú. Verifica el eco **antes** de cada `--enter`: un Enter con la línea vacía acepta
la opción por defecto y redibuja el menú, que parece que no hizo nada.

Si el disco trae `em0/em1` y el nodo arranca con `virtio-net-pci`, pfSense entra en bucle de
«interface mismatch»: páralo y cambia el adaptador.

```bash
gns3lab down examen-kit --keep-open
gns3lab node props PF1 -p examen-kit --set adapter_type=e1000
gns3lab up examen-kit
```

Confirma: `PF1: {..."adapter_type": "e1000"} -> OK`, y tras `up`, el menú en vez del bucle.

## 5. VLANs en el switch

El switch de GNS3 se configura por API con el mapa de puertos:

```bash
gns3lab node switch SW1 -p examen-kit --port 0=dot1q:43 --port 1=access:20 --port 2=access:30
```

Confirma: `SW1: N puertos -> OK`. Cada `--port` es `número_de_puerto=tipo[:vlan]`; el troncal
lleva `dot1q` y los de acceso, `access`. Los puertos no listados conservan su valor anterior.

El enlace del firewall al switch debe ir por el puerto troncal:

```bash
gns3lab link list -p examen-kit
```

Confirma: la línea `PF1:1/0 <-> SW1:0/0` (adaptador 1 del firewall contra el adaptador 0 del
switch). En un switch, el segundo número de `--pb`/`--ppb` es el puerto: `--pb 0 --ppb 0` es
Ethernet0, el troncal del ejemplo.

En pfSense, la VLAN se crea desde el mismo menú de asignación: opción `1`, responder que sí a
configurar VLANs, elegir la interfaz padre (la LAN) y el tag `43`; después asignar la VLAN nueva
a `OPT1`. Se lee igual que el paso 4:

```bash
gns3lab shot PF1 -p examen-kit
gns3lab type PF1 "1" --enter -p examen-kit
gns3lab shot PF1 -p examen-kit
```

Confirma: el resumen de interfaces incluye `OPT1 (opt1) -> vtnet1.43` (o el nombre que use el
disco) y vuelve al menú.

La OPT bloquea todo por defecto. Para que pase tráfico, en la shell (opción `8`):

```bash
gns3lab type PF1 "8" --enter -p examen-kit
gns3lab shot PF1 -p examen-kit
gns3lab type PF1 "easyrule pass opt1 any any any" --enter -p examen-kit
gns3lab shot PF1 -p examen-kit
```

Confirma: la captura muestra la regla creada, sin `Missing parameters`. `easyrule` con un
argumento menos da ese error. El orden del array de reglas manda: una `reject` antes deja inerte
tu `pass`.

## 6. Verificar con ping y doctor

Conectividad de las VPCS, que es lo que se enseña:

```bash
gns3lab test examen-kit
```

Confirma: el bloque `gateway` con la IP real (`192.168.1.1`) y el bloque `conectividad` con
`OK` en PC↔PC, PC→gateway y PC→`8.8.8.8`, sin ningún `FALLO`. Código 0.

Ping explícito desde un PC:

```bash
gns3lab exec PC1 "ip dhcp" "show ip" "ping 192.168.1.1" "ping 8.8.8.8" -p examen-kit
```

Confirma: `show ip` con `IP/MASK` distinta de `0.0.0.0`, y en cada ping `0% packet loss`. Si el
campo gateway de `show ip` muestra `255.255.255.0`, es un fallo de pintado del cliente VPCS: el
gateway bueno es el `DHCP SERVER` del mismo `show ip`.

Chequeo integral:

```bash
gns3lab doctor examen-kit
```

Confirma: todos los nodos `started`, `console=...` en cada uno, y `resumen` con `sin hallazgos`.
Código 0. Cualquier línea `- ...` es un problema que hay que resolver antes de entregar.

## 7. Llevarlo al servidor del aula

```bash
gns3lab -s clase port examen-kit --from local --name "Pablo Rodriguez" --start
```

Confirma, en este orden:

```text
origen : local — examen-kit (xxxxxxxx)
destino: clase — http://192.168.71.250:80
  export: N KB, N nodos, N enlaces
  discos que faltan en el destino: pfSense-examen.qcow2
  subiendo pfSense-examen.qcow2 (N MB)...
    OK
  correcciones:
  importado como 'Pablo Rodriguez' (xxxxxxxx)
  abierto: N nodos, N enlaces
```

y la lista de nodos con `started`. El nombre del proyecto debe casar con el `matcher` de la
config (`Pablo Rodriguez`) para que los comandos siguientes lo encuentren sin ambigüedad entre
los proyectos abiertos de los compañeros.

Verifica ya en el servidor del aula:

```bash
gns3lab -s clase doctor "Pablo Rodriguez"
gns3lab -s clase test "Pablo Rodriguez"
```

Confirma: `sin hallazgos` y todas las líneas `OK`. `doctor` en el aula avisa si un nodo QEMU no
tiene monitor HMP visible, que es normal si el proceso corre con otro usuario; en ese caso `shot`
y `key` no funcionan allí y hay que quedarse con la consola telnet o el VNC.

Si el aula no deja subir imágenes, el disco tiene que existir ya en el servidor; si no, `import`
repunta a un `empty*.qcow2` e instala desde el ISO, que son los 40 minutos que este kit evita.

## Lista final

| # | Comprobación | Comando | Señal de OK |
|---|---|---|---|
| 1 | servidor | `gns3lab servers` | `[OK ] local` |
| 2 | kit arrancado | `gns3lab status examen-kit` | todos `started` |
| 3 | menú pfSense | `gns3lab shot PF1 -p examen-kit` | opciones 1/2/8 en el texto |
| 4 | interfaces | `gns3lab shot PF1` tras cada respuesta | `WAN -> em0`, `LAN -> em1` |
| 5 | VLANs | `gns3lab node switch SW1 ...` | `SW1: N puertos -> OK` |
| 6 | conectividad | `gns3lab test examen-kit` | todo `OK`, 0 % pérdida |
| 7 | integral | `gns3lab doctor examen-kit` | `sin hallazgos` |
| 8 | portado | `gns3lab -s clase port ...` | `importado como ...`, nodos `started` |
| 9 | aula | `gns3lab -s clase doctor ...` | `sin hallazgos` |
