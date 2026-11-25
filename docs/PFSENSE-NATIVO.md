# pfSense nativo: de la consola a `config.xml`

Secciones: Estado en este árbol · 1. Detectar los nombres de interfaz · 2. Credenciales: sólo variables de entorno · 3. Orden de la configuración nativa · 4. El menú: sólo cuando aún no hay SSH · 5. Verificación con salida real · 6. Errores literales y su causa.

La vía nativa habla el formato que pfSense entiende de verdad: `/conf/config.xml` y sus
comandos (`pfctl`, `ifconfig`, `easyrule`, `/etc/rc.reload_all`) por SSH. El VNC queda para el
primer arranque sin SSH y para instaladores con ratón; antes de abrirlo, agota consola telnet y
monitor HMP ([EXAMEN.md](EXAMEN.md), [TROUBLESHOOTING.md](TROUBLESHOOTING.md)).

## Estado en este árbol

Los comandos `gns3lab pf` y el módulo `pfsense.py` existen y están cubiertos por
`tests/test_pfsense.py` y `tests/test_cli_pf.py`. Las firmas documentadas abajo salen de
`pfsense.py` (`PfSense.*`) y de `gns3lab pf <acción> --help`; las que no se han ejecutado contra
un firewall real se marcan como tales. `gns3lab shot/type/key`, `exec`, `node props` y `doctor`
también están en el árbol. Comprueba siempre `gns3lab pf --help` antes de dar un comando por
bueno.

## 1. Detectar los nombres de interfaz

```bash
gns3lab pf detect -p examen-kit --json
```

`detect` sólo lee el nodo del proyecto: no usa SSH ni credenciales. `detect_ifnames()` lee
`node["properties"]["adapter_type"]` y devuelve `{"wan": ..., "lan": ...}`:

- `e1000` → el invitado ve `em0` (WAN) y `em1` (LAN).
- `virtio-net-pci` → el invitado ve `vtnet0` y `vtnet1`.

**Por qué `e1000` corta el bucle «interface mismatch»**: el disco trae `em0/em1` escritos en el
`config.xml`. Si el nodo arranca con `virtio-net-pci`, el kernel de FreeBSD presenta `vtnet0/1`,
pfSense busca `em0/em1`, no los encuentra y vuelve al menú de asignación una y otra vez. Poner
el adaptador a `e1000` hace que el invitado vea de nuevo `em0/em1`, que es lo que el disco
espera:

```bash
gns3lab down examen-kit --keep-open
gns3lab node props PF1 -p examen-kit --set adapter_type=e1000
gns3lab up examen-kit
```

Arrancar y parar nodos cambia el estado del laboratorio: dilo en el informe final.

## 2. Credenciales: sólo variables de entorno

`PfSense.from_env()` lee los nombres; nunca valores escritos en un fichero versionado ni en un
comando con el secreto en la línea:

| Variable | Uso |
|---|---|
| `PFSENSE_HOST` | IP del firewall; por defecto `192.168.1.1` |
| `PFSENSE_PORT` | puerto SSH; por defecto `22022` |
| `PFSENSE_USER` | usuario SSH; por defecto `admin` |
| `PFSENSE_PASSWORD` | obligatoria; si falta, el error nombra la variable, nunca su valor |

Para no dejarla en el historial de la shell, léela de forma interactiva y expórtala:

```bash
read -rsp 'Contraseña de pfSense: ' PFSENSE_PASSWORD; echo
export PFSENSE_PASSWORD
```

Las credenciales del **servidor GNS3** son otra cosa: se leen en tiempo de ejecución de
`~/.config/GNS3/2.2/gns3_server.conf`. Ninguna de las dos se copia al repo, a un markdown ni a
un commit.

## 3. Orden de la configuración nativa

Ejemplo con una LAN `192.168.1.0/24` y el firewall en `192.168.1.1` (cambia las IP por las de
tu escenario). Cada orden delega en el método del contrato de `pfsense.py`:

```bash
# 1. Asignar WAN/LAN (y OPT1 si hay VLAN) sobre los nombres reales.
gns3lab pf assign --wan em0 --lan em1

# 2. IP de la LAN y, si procede, gateway.
gns3lab pf ip em1 192.168.1.1 24

# 3. Rango DHCP para los clientes de esa LAN.
gns3lab pf dhcp em1 192.168.1.100 192.168.1.200

# 4. Regla de paso. El orden del array manda: entra antes de cualquier reject.
gns3lab pf rule pass --if lan --proto tcp --src any --dst any --port 80

# 5. NAT de salida por la WAN.
gns3lab pf nat --if wan

# 6. Habilitar SSH (por defecto en el puerto 22022).
gns3lab pf ssh --port 22022
```

`assign()` comprueba que el nombre existe en `ifconfig` antes de escribirlo: si no, devuelve un
error con los nombres disponibles. `rule()` y `nat()` insertan **antes** de cualquier `reject`
existente. `put_config()` hace copia de seguridad (`config.xml.bak-<stamp>`) y recarga con
`/etc/rc.reload_all`; no borra secciones del XML que no entiende. Para inspeccionar o guardar
la configuración:

```bash
gns3lab pf config get > fw.xml
gns3lab pf config put fw.xml --yes
```

Añade `--json` a cualquier orden `pf` para obtener un objeto parseable con `ok` y `data`.

## 4. El menú: sólo cuando aún no hay SSH

Si el firewall todavía no responde por SSH, se usa el monitor HMP, no VNC. El orden de lectura
es siempre `shot` → `type`/`key` → `shot`, y se comprueba el eco antes de cada `ret`:

```bash
gns3lab shot PF1 -p examen-kit
gns3lab type PF1 "1" --enter -p examen-kit
gns3lab shot PF1 -p examen-kit
```

Las respuestas de asignación se escriben con los nombres que muestra la propia captura
(`em0`/`em1` con `e1000`, `vtnet0`/`vtnet1` con virtio). Para una regla rápida desde la shell
del menú (opción `8`):

```bash
gns3lab type PF1 "8" --enter -p examen-kit
gns3lab shot PF1 -p examen-kit
gns3lab type PF1 "easyrule pass opt1 any any any" --enter -p examen-kit
gns3lab shot PF1 -p examen-kit
```

Trampas ya pagadas, no repetirlas: `sendkey ret`, no `enter`; mayúsculas y símbolos con
`shift-<tecla>`; la consola del invitado se come la primera tecla y `type` ya envía `sendkey
shift`; OCR a escala x2 y `--psm 4`, porque a x1 confunde `w` con `u`; `screendump` escribe un
PPM con extensión `.png` y `shot` lo convierte. Una vez que SSH responde, el menú ya no hace
falta: `gns3lab pf ssh` y los órdenes de la sección 3 lo sustituyen.

## 5. Verificación con salida real

```bash
gns3lab pf status                       # versión, ifconfig, pfctl -sr y rutas desde el firewall
gns3lab doctor examen-kit               # debe terminar en «sin hallazgos»
gns3lab exec PC1 "ip dhcp" "show ip" "ping 192.168.1.1" -p examen-kit --idle 4
```

La prueba de red es `0% packet loss` en el ping y una IP distinta de `0.0.0.0` en `show ip`;
`gns3lab test examen-kit` comprueba además PC↔PC, PC→gateway y PC→`8.8.8.8`. Un `200 OK` de la
API no prueba conectividad.

## 6. Errores literales y su causa

Salidas tomadas de [TROUBLESHOOTING.md](TROUBLESHOOTING.md) y [EXAMEN.md](EXAMEN.md). Las dos
últimas son mensajes de `pfsense.py`; no se han reproducido contra un firewall real.

| Salida literal | Causa | Arreglo |
|---|---|---|
| `pfSense repite «interface mismatch» en bucle` | disco con `em0/em1` y nodo con `virtio-net-pci` | `pf detect`, luego `node props PF1 --set adapter_type=e1000` y rearrancar |
| `Missing parameters` (`easyrule`) | falta un argumento en `easyrule` | pasar los cuatro argumentos: acción, interfaz, src, dst |
| `no encuentro el monitor del nodo QEMU` | nodo parado o proceso de otro usuario | `gns3lab up`; `shot`/`key` sólo ven `/proc` del compute local |
| `sin traducción a tecla: [...]` | carácter no ASCII en `type` | ASCII imprimible, o `key` con el nombre HMP |
| `Port 1/0 for SW1 not found` | puerto del switch pasado como adaptador | el puerto va en `--ppb`: `link add PF1 SW1 --pb 0 --ppb 1` |
| `gateway=255.255.255.0` | VPCS pinta la máscara en el campo gateway | `test` usa el `DHCP SERVER` de `show ip` y reconfigura la IP |
| `gateway=... y sin concesión DHCP; revisa pfSense` | DHCP caído, VLAN o asignación de OPT incorrectas | revisar `node switch`, la asignación y la regla `pass` en OPT |
| `sin tesseract` / `sin Pillow: el screendump queda en PPM` (avisos de `doctor`) | faltan binarios | instalarlos; sin ellos `shot` da la imagen pero el OCR queda vacío |
| `falta la variable de entorno PFSENSE_PASSWORD` | no está exportada | exportarla sin escribir su valor en ficheros ni comandos |
| error de `assign()` con los nombres disponibles | el `if` pedido no existe en `ifconfig` | usar un nombre real de `pf detect` o cambiar `adapter_type` |

Referencia corta para la skill: [skill-sync/references/pfsense-nativo.md](../skill-sync/references/pfsense-nativo.md).
El batch del MCP, en [MCP-VELOCIDAD.md](MCP-VELOCIDAD.md). Flags de la CLI, en
[COMANDOS.md](COMANDOS.md).
