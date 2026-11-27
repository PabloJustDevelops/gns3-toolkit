# Recomendaciones para el flujo de examen de pfSense/VPN

Fecha: 2026-11-27. Alcance revisado: `docs/EXAMEN.md`, `docs/PFSENSE-NATIVO.md`,
`docs/CAPTURAS-EXAMEN.md`, `cli/gns3lab examen`, `pfsense.py` y las pruebas de examen/capturas.

La revisión ha sido de sólo lectura: no se ha creado, arrancado, parado, importado ni borrado
ningún nodo o proyecto. Las recomendaciones parten de una imagen pfSense ya preparada y clonada
mediante linked clone; no proponen instalar pfSense desde ISO. El orden de consola sigue siendo
telnet → monitor HMP → VNC únicamente como último recurso.

## Evidencia de la revisión

- `examen setup` ya fija `linked_clone=True` y `console_type=telnet` por defecto
  (`cli/gns3lab:3519`, `cli/gns3lab:3580-3605`).
- `examen verify` ya comprueba el linked clone (`cli/gns3lab:3692`, `cli/gns3lab:3733-3736`), pero
  no los enlaces, el mapa de puertos del switch ni la VPN.
- `pf detect` deduce `em0/em1` o `vtnet0/vtnet1`, pero su JSON no incluye `adapter_type`
  (`cli/gns3lab:4221-4229`), un campo que `scripts/labspec.py:532-548` sí espera.
- Las capturas por consola/WebUI y la tool MCP ya existen, aunque `docs/CAPTURAS-EXAMEN.md:13-28`
  y `docs/EXAMEN.md:32-35` todavía las presenten como ausentes o previstas. La ruta CLI de
  `examen capturas` aún no escribe `indice.md`.
- No hay comprobación de VPN en la documentación ni en `cli/gns3lab`: una búsqueda de
  `VPN|IPsec|OpenVPN|WireGuard` sólo encuentra el nombre del proyecto `Practica VPN` en notas de
  orquestación, no un contrato de verificación ejecutable.
- Gates de base ejecutados en esta sesión:
  - `.venv/bin/python -m pytest -q tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense`
    → exit 0, `3 passed in 0.94s`.
  - `.venv/bin/python -m pytest -q tests/test_exam_cli.py` → exit 0, `3 passed in 1.04s`.
  - `.venv/bin/python -m pytest -q tests/test_captures.py tests/test_webui_capture.py tests/test_mcp_capturas.py`
    → exit 0, `56 passed in 1.07s`.
  - `.venv/bin/python scripts/verify.py` → exit 0, `OK: sin deriva`.
  - `.venv/bin/python scripts/check-links.py` → exit 0, `OK: sin enlaces rotos`.

## Recomendaciones (8, ordenadas por impacto y dependencias)

### 1. Unificar el nombre del proyecto en todo el guion — esfuerzo bajo, impacto alto

**Hallazgo.** `docs/EXAMEN.md:9` dice «El proyecto se llama `examen`», `:16-18` crea `Kit de
examen`, pero `:32`, `:69-84` y `:224` usan `examen-kit`. `Server.resolve_project()` hace coincidencia
por substring (`gns3core.py:246-260`), pero `examen-kit` no casa con `Kit de examen`: el atajo puede
dejar todos los comandos posteriores apuntando a un proyecto inexistente.

**Cambio concreto.** Fijar `examen-kit` como nombre canónico del guion y pasarlo siempre de forma
explícita, también en `shot`, `node switch`, `test`, `port`, `doctor` e `informe`:

```bash
PROJECT='examen-kit'
BASE='Practica VPN'   # sustituir por el proyecto base real
./cli/gns3lab examen setup --name "$PROJECT" --from "$BASE" --console-type telnet
./cli/gns3lab examen verify --name "$PROJECT" --json
./cli/gns3lab status "$PROJECT"
```

**Criterio de verificación.** `status "$PROJECT"` muestra el mismo proyecto creado por `setup`; el
JSON de `examen verify` devuelve `project.name == "examen-kit"` y `ok: true`. Ningún comando del
guion debe mezclar `examen`, `examen-kit` y `Kit de examen` para el mismo laboratorio.

### 2. Añadir un preflight de clon/adaptador y corregir `pf detect` — esfuerzo bajo, impacto alto

**Hallazgo.** La base ya usa linked clone, pero `docs/PFSENSE-NATIVO.md:6-13` todavía habla de VNC
para instalar el ISO y `docs/EXAMEN.md:256-257` contempla `empty*.qcow2` e instalación desde ISO.
Además, `docs/EXAMEN.md:74` espera `vnc:5901` aunque PF1 se crea con telnet. `pf detect` no devuelve
`adapter_type`, por lo que `lab verify` puede reportar `adapter_type=?` incluso con un nodo correcto.

**Cambio concreto.** Añadir una acción de sólo lectura `examen preflight` y hacer que `setup` la
ejecute antes de escribir en GNS3. Debe exigir `--from` (o una imagen explícita), rechazar ISO y
`empty*.qcow2`, aceptar sólo telnet para el perfil de examen y validar el `adapter_type` del nodo
base/marker antes de arrancar. Añadir `adapter_type` al JSON de `_pf_detect`, guardarlo en
`examen-setup.json` y contrastarlo en `examen verify`.

```bash
# Comando propuesto; no existe todavía.
./cli/gns3lab examen preflight --name "$PROJECT" --from "$BASE" --console-type telnet --json

# Comandos existentes tras el montaje.
./cli/gns3lab pf detect -p "$PROJECT" --json
./cli/gns3lab examen verify --name "$PROJECT" --json
```

**Criterio de verificación.** El preflight debe incluir imagen base, overlay, `linked_clone: true`,
`console_type: telnet`, `adapter_type` y `wan/lan`. Si no hay imagen clonable, debe salir distinto de
0 antes de crear el proyecto. `pf detect --json` debe devolver, por ejemplo,
`{"adapter_type":"e1000","wan":"em0","lan":"em1"}`. La cadena de backing de QEMU debe mostrar un
overlay distinto y el hash de la base no debe cambiar. Un disco `em0/em1` con `virtio-net-pci` debe
fallar con el comando exacto para fijar `adapter_type=e1000`.

### 3. Crear un checkpoint antes del primer arranque y permitir rollback — esfuerzo medio, impacto alto

**Hallazgo.** `examen setup` arranca los nodos en `cli/gns3lab:3658` sin snapshot previo. El guion
manual crea el snapshot después de `up` (`docs/EXAMEN.md:78-84`), cuando pfSense ya puede haber
arrancado y modificado el disco. `examen reset` sólo reinicia nodos (`cli/gns3lab:3783`), no restaura
la configuración base.

**Cambio concreto.** Añadir `examen setup --snapshot base-limpia`: crear el snapshot después de
escribir `examen-setup.json` y antes de `nodes_action("start")`, guardar su nombre en el marker y
mostrarlo en `verify`. Añadir `examen rollback` con la misma protección de marker que `reset`.

```bash
# Forma propuesta del setup; el flag no existe todavía.
./cli/gns3lab examen setup --name "$PROJECT" --from "$BASE" --snapshot base-limpia

# Comando propuesto; no existe todavía.
./cli/gns3lab examen rollback --name "$PROJECT" --snapshot base-limpia --yes
```

**Criterio de verificación.** `snap list "" "$PROJECT"` muestra `base-limpia`; el JSON de `verify`
incluye `checks.backup.ok: true` y ese snapshot. Después de modificar una regla o VLAN, `rollback`
devuelve el laboratorio al estado base y `examen verify` vuelve a pasar. Si falta la marca de
`gns3lab examen setup`, el rollback debe abortar sin parar ni restaurar nada. Snapshot y rollback
deben reportarse como cambios de estado.

### 4. Automatizar el bootstrap hasta SSH con espera activa por HMP — esfuerzo medio, impacto alto

**Hallazgo.** `docs/EXAMEN.md:108-131` escribe a ciegas entre captura y captura. Además,
`docs/PFSENSE-NATIVO.md:83-101` presenta `pf assign` como primer paso, pero esos comandos usan SSH;
el propio documento reserva el menú para cuando todavía no hay SSH (`:116-142`). Falta una frontera
clara y automatizada entre bootstrap y configuración nativa.

**Cambio concreto.** Añadir `examen bootstrap`, implementado con `pf detect`, `QemuMonitor` y la
consola telnet. Debe esperar por OCR hasta encontrar el menú (`1) Assign Interfaces`, `8) Shell`),
enviar `type/key` sólo cuando la pantalla espera una respuesta, configurar WAN/LAN y una LAN mínima,
habilitar SSH y salir. Debe detectar «interface mismatch» y abortar con la corrección de adaptador;
no debe usar sleeps fijos ni VNC.

```bash
# Comando propuesto; no existe todavía.
./cli/gns3lab examen bootstrap --name "$PROJECT" --json
```

**Criterio de verificación.** Exit 0 sólo cuando `gns3lab pf status --json` responde por SSH con
`ok: true` y contiene las interfaces esperadas. Una prueba con OCR de «interface mismatch» debe
terminar en error y sugerir `node props PF1 --set adapter_type=e1000`; una prueba con el menú
incompleto debe reintentar hasta timeout sin enviar teclas prematuras.

### 5. Usar la vía nativa completa después del bootstrap — esfuerzo bajo, impacto medio

**Hallazgo.** `docs/EXAMEN.md:165-185` sigue usando el menú y `easyrule` para VLAN/reglas, mientras
`docs/PFSENSE-NATIVO.md:78-114` ya ofrece edición nativa de `config.xml` con backup y recarga. Cada
paso por menú añade capturas, teclas y riesgo de aceptar valores por defecto.

**Cambio concreto.** Tras habilitar SSH, sustituir el menú por los comandos existentes, con
`PFSENSE_HOST`, `PFSENSE_USER` y `PFSENSE_PASSWORD` exportados. `put_config()` ya crea el backup
remoto `config.xml.bak-<stamp>`; no hace falta volcar `config.xml` al repo ni dejarlo en un Markdown.

```bash
./cli/gns3lab pf assign --wan em0 --lan em1
./cli/gns3lab pf ip em1 192.168.1.1 24
./cli/gns3lab pf dhcp em1 192.168.1.100 192.168.1.200
./cli/gns3lab pf rule pass --if lan --proto tcp --src any --dst any --port 80
./cli/gns3lab pf nat --if wan
./cli/gns3lab pf status --json
```

La opción `8) Shell` y `easyrule` quedan sólo como diagnóstico de emergencia, no como ruta normal.

**Criterio de verificación.** Cada comando devuelve `ok: true` y `put_config()` reporta su backup
remoto; `pf status` muestra IP, reglas y rutas esperadas; `pf config get` conserva las secciones
WAN/LAN/OPT, `filter` y `nat`; `gns3lab test "$PROJECT"` termina con todos los `OK` y `0% packet
loss`. El flujo normal no debe contener `type PF1 "8"` ni `easyrule`.

### 6. Hacer que `examen verify` compruebe enlaces y VLAN, no sólo ping — esfuerzo medio, impacto alto

**Hallazgo.** `docs/EXAMEN.md:17` describe `examen verify` como «estado, enlaces y ping real», pero
`cli/gns3lab:3692-3780` sólo comprueba `started`, linked clone, disco compartido, NAT y ping a
Internet. No contrasta los cuatro enlaces creados en `:3619-3622` ni el mapa de puertos del switch.
Tampoco reutiliza el reintento DHCP de `cmd_test`, por lo que puede dar un falso rojo justo después
del montaje.

**Cambio concreto.** Añadir `checks.links` y `checks.vlan` a `_examen_verify`: leer los enlaces con
`json_list_or_die`, normalizar extremos como en `scripts/labspec.py:487-502` y comparar el mapa de
puertos esperado del switch. Reutilizar el reintento DHCP antes del ping. Si se documenta `verify`
como sólo lectura, sustituir `ensure_open` por una comprobación de proyecto abierto o declarar
explícitamente que abre el proyecto.

**Criterio de verificación.** `examen verify --json` devuelve
`checks.links == {"ok": true, "count": 4}` y el mapa VLAN esperado. Al quitar un enlace debe aparecer
`falta PF1:1/0 <-> SW1:0/0` en `problems` y el exit code debe ser distinto de 0. Un puerto de acceso o
troncal incorrecto debe producir un problema con puerto y VLAN literales.

### 7. Incorporar una verificación VPN de extremo a extremo — esfuerzo medio, impacto alto

**Hallazgo.** `VERIFY_COMPONENTS` sólo contiene `qemu/pf/vpcs` (`gns3core.py:1305`) y no hay acción
VPN en `pf` ni en `examen verify`. Un ping a Internet puede pasar aunque la VPN esté caída.

**Cambio concreto.** Registrar `vpn` en `VERIFY_COMPONENTS` y añadir `_verify_vpn_checks()` junto a
`_verify_pf_checks`, reutilizando `PfSense.status()` y `get_config()`. Debe comprobar la sección VPN
de `config.xml`, la interfaz túnel en `ifconfig`, una regla `pass` en `pfctl -sr`, la ruta a la
subred remota en `netstat -rn` y un ping desde VPCS a la IP del peer/túnel. Exponer el resultado en
`examen verify` sin escribir en pfSense.

```bash
# Comandos propuestos; no existen todavía.
./cli/gns3lab verify vpn "$PROJECT" --json
./cli/gns3lab -s clase verify vpn "Pablo Rodriguez" --json
```

**Criterio de verificación.** El JSON debe separar `checks.network` y `checks.vpn`. `checks.vpn.ok`
sólo puede ser verdadero si el peer/SA aparece activo, existe la interfaz y la ruta esperadas, y el
ping termina en `0% packet loss`. Un peer detenido, una SA ausente o un túnel sin tráfico deben
producir `ok: false` y un motivo literal. La salida no debe contener `PFSENSE_PASSWORD`, PSK ni
material privado.

### 8. Cerrar el contrato CLI de capturas y actualizar la documentación — esfuerzo medio, impacto medio

**Hallazgo.** `docs/CAPTURAS-EXAMEN.md:13-28` dice que faltan `captures.py`, `webui_capture.py`,
`gns3lab examen capturas` y `gns3_capturas`, pero los cuatro existen. La ruta CLI de
`examen capturas` sólo llama a `capture_phase` (`cli/gns3lab:4008-4036`): no escribe `indice.md`,
tiene PF1 fijado y con `--webui` ignora `--phase`. `scripts/labspec.py` ya acepta `captures=True`,
pero `lab apply/verify` no exponen el flag.

**Cambio concreto.** Añadir `--node` (default `PF1`), acumular entradas de consola/WebUI y llamar a
`captures.write_index()`; derivar de `--phase` las páginas WebUI y etiquetar cada entrada. Cablear
`--captures` en `lab apply` y `lab verify`, seleccionando por defecto un nodo QEMU y no el primer
nodo de la spec. Añadir `examples/examen.yaml` con el bloque `captures:` y PF1 explícito.
Actualizar las tablas de estado y distinguir lo existente de lo todavía ausente.

```bash
# Existente hoy para una fase de consola; todavía sin índice.
./cli/gns3lab examen capturas --name "$PROJECT" --phase verificacion \
  --out "$HOME/GNS3/capturas" --json

# Forma propuesta tras completar el contrato CLI.
./cli/gns3lab examen capturas --name "$PROJECT" --node PF1 --phase verificacion \
  --out "$HOME/GNS3/capturas" --json
./cli/gns3lab lab verify --spec examples/examen.yaml --captures --json
```

**Criterio de verificación.** El directorio contiene un PNG por fase y `indice.md` con cinco filas
como máximo, `fallos: 0` y OCR no vacío para pfSense. Con `--webui` aparecen las filas
`interfaces`, `rules` y `dhcp`; sin Playwright debe conservarse `fallback=consola` con la razón.
`lab apply/verify --help` deben listar `--captures` y la suite de capturas debe terminar con exit
0. La WebUI queda como evidencia opcional de sólo lectura, nunca como configuración.

## Límites

No se ha validado ninguna recomendación nueva contra pfSense o un peer VPN real. Los comandos
marcados como propuestos son cambios de CLI pendientes de implementar; los comandos existentes se
han contrastado con `--help`, código y pruebas. No se ha usado VNC ni se ha instalado pfSense desde
ISO.
