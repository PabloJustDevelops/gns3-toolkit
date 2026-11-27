# Recomendaciones Hy4 — auditoría de código

Fecha: 2026-11-27. Alcance: `pfsense.py`, `gns3core.py`, `gns3_mcp_server.py`,
`cli/gns3lab`, `scripts/labspec.py`, `scripts/check-links.py` y los informes de
`orchestration/auditorias/`.

Revisión de sólo lectura con dobles en memoria: no se arrancó ni paró ningún nodo, no se
llamó a un servidor GNS3 ni a un pfSense real, y no se hizo commit ni PR. Las credenciales
usadas en las reproducciones son cadenas sintéticas (`CLAVE`, `admin-SECRETO`).

## Evidencia de la revisión

Todas las salidas siguientes se obtuvieron en esta sesión con `.venv/bin/python` o `python3`:

- `_asegurar_wan` con un QEMU de dos adaptadores y adapter 0 libre → `NameError: name 'uuid' is not defined`; `"uuid" in vars(cli)` → `False`.
- `cmd_all(args(json=True), {})` con cliente falso → stdout `'demo: start [200] — started=1\n'`, `rc=0` (la opción local `--json` no se consulta).
- `cmd_images` con lista vacía → `{"count": 0, "images": []}`, `rc=0`; `cmd_snap(list)` → `sin snapshots`, `rc=0`.
- `PfSense(password=<de entorno>).get_config()` con XML `<hostname>CLAVE</hostname>` → `{'system': {'hostname': '***'}}`.
- `_lab_redact("error: admin-SECRETO")` con usuario `admin` y contraseña `admin-SECRETO` → `error: [redactado]-SECRETO`.
- `Console.run("show ip", expect="READY", idle=.001)` con EOF inmediato → `{'output': '', 'ok': True, 'timed_out': False}`.
- `_batch_block_reason` devuelve `None` para `gns3_nodes/delete`, `gns3_template/delete`, `gns3_snapshots/delete`, `gns3_snapshots/restore` y `gns3_drawings/clear`.
- `urllib.request.Request(.../files/config#backup.txt).selector` → `/v2/projects/p/nodes/n/files/config` (el sufijo se pierde como fragmento).
- `python3 scripts/verify.py` → `comandos=48 tools=50 áreas=12` y `OK: sin deriva`.
- `python3 scripts/check-links.py` → `ROTO: 23 hallazgos`, exit 1; los 23 están en los tres informes `codex-*.md`.

## Recomendaciones (8, ordenadas por impacto)

### 1. No redactar la contraseña dentro del XML leído — prioridad alta

**Hallazgo.** `pfsense.py:227-231` redacta sustituyendo la contraseña por `***`, y
`pfsense.py:263-264` aplica esa redacción a todo el `stdout`; `pfsense.py:292-300` parsea
ese mismo `stdout` como `config.xml`. Con una contraseña que aparezca como valor del XML,
`get_config()` devuelve el valor corrupto (`{'system': {'hostname': '***'}}`), y cualquier
`put_config()` posterior (`pfsense.py:302-358`) puede escribir `***` en la configuración
real. Si la coincidencia cae en una etiqueta, el XML deja de parsearse.

**Cambio concreto.** Redactar `error`, `stderr` y `cmd` (canales de diagnóstico), pero no
`output` cuando el comando es `cat /conf/config.xml`. Formalizarlo con un parámetro
`redact_output=True` en `PfSense.run()` y pasar `False` desde `get_config()`; añadir un test
con una contraseña sintética presente en un valor y en una etiqueta del XML.

**Criterio de verificación.** Con password de prueba `CLAVE` y XML que contenga
`<hostname>CLAVE</hostname>`, `get_config()` devuelve `hostname == 'CLAVE'` y `ok` no es
`False`; `put_config()` no contiene `***`; un error de SSH con la contraseña en `stderr`
sigue sin filtrarla. Sin escribir en un firewall real: sólo dobles.

### 2. Redactar primero el secreto más largo — prioridad alta

**Hallazgo.** `gns3_mcp_server.py:569-585` itera `GNS3_USER` antes que `GNS3_PASSWORD`
(`:572`) y `user` antes que `password` (`:579-582`). Si el usuario es prefijo de la
contraseña, la primera sustitución deja el sufijo visible: reproducido
`error: [redactado]-SECRETO`. `_redact_informe` (`gns3_mcp_server.py:4000-4015`) repite el
mismo orden con `user`/`password`, por lo que un informe Markdown puede filtrar el resto.

**Cambio concreto.** Un único helper de redacción que ordene los secretos por longitud
descendente, elimine duplicados y vacíos, y lo usen `_lab_redact`, `_capture_redact_result`
y `_redact_informe`. Mantener las pasadas finales de URL con credenciales y `Basic …`.

**Criterio de verificación.** Con `GNS3_USER=admin` y password sintética `admin-SECRETO`,
`_lab_redact`, `_lab_redact_any` (incluido un dict anidado) y `_redact_informe` devuelven
texto sin `SECRETO` ni `[redactado]-SECRETO`. Los tests de redacción existentes
(`tests/test_mcp_lab.py`, `tests/test_mcp_capturas.py`) siguen pasando con el caso solapado
añadido.

### 3. `ok` de consola debe exigir `expect` y descartar EOF — prioridad alta

**Hallazgo.** `gns3core.py:974-1036` calcula `ok = not timed_out` (`:1036`). El bucle sale
por `self.closed` (`:998`) o por quietud (`:1021-1022`) sin marcar fallo, aunque `expect`
no aparezca. Reproducido: EOF inmediato con `expect='READY'` → salida vacía, `ok=True`,
`timed_out=False`. `run_many()` (`gns3core.py:1038-1047`) sólo corta por `timed_out`, y
`gns3_exec` (`gns3_mcp_server.py:2457-2515`) devuelve `failed: []`. Una verificación puede
declarar exitosa una consola que nunca contestó.

**Cambio concreto.** Calcular
`ok = not timed_out and not closed and (not expect or re.search(expect, buf) is not None)`;
añadir `eof` y `matched` al resultado; hacer que `run_many()` pare también en `not ok` o
`eof`, y que `gns3_exec` refleje el motivo en `failed`.

**Criterio de verificación.** EOF y `expect` no encontrado → `ok:false`, `eof:true` o
`matched:false`, y el comando aparece en `failed`; un comando con prompt normal → `ok:true`.
Los tests de consola (`tests/test_console.py`, `tests/test_console_extra.py`) pasan con los
nuevos campos.

### 4. Cerrar los borrados sin `confirm` en `gns3_batch` — prioridad alta

**Hallazgo.** `_batch_block_reason` (`gns3_mcp_server.py:3784-3806`) es una lista negra
incompleta. Verificado que devuelve `None` para `gns3_nodes(action='delete', node='*')`,
`gns3_template(action='delete')`, `gns3_snapshots(action='delete'|'restore')` y
`gns3_drawings(action='clear')`; las tools existen y escriben en
`gns3_mcp_server.py:1507`, `:1322`, `:2258` y `:2858`. `gns3_batch` (`:3920`) ejecuta esas
operaciones sin `confirm` y las clasifica como no paralelas pero ejecutables.

**Cambio concreto.** Invertir la regla: por defecto toda tool con `action` no incluida en
una lista explícita de lectura (`_batch_is_read_only`, `:3814`) exige `confirm=True` si su
nombre o acción contiene `delete`, `restore`, `clear`, `import` o `apply`. Añadir esas cinco
tools a `_batch_block_reason` como mínimo.

**Criterio de verificación.** Las cinco operaciones anteriores sin `confirm` →
`results[i].ok == false` con «requiere confirm=True en la operación» y ninguna llamada a la
tool; con `confirm: true` → ejecutan. `pytest -q tests/test_batch.py` termina exit 0.

### 5. Importar `uuid` en `_asegurar_wan` antes de usarlo — prioridad media-alta

**Hallazgo.** `cli/gns3lab:1179` define `_asegurar_wan` y en `cli/gns3lab:1201` llama a
`uuid.uuid4()`, pero el módulo no importa `uuid`: sólo hay imports locales en
`cmd_fix` (`:1301`), `cmd_import` (`:1354`, `:1442`) y los llamadores (`:1369`, `:1513`).
Un import local del llamador no entra en los globals del helper. Reproducido con un
QEMU de dos adaptadores sin enlace en adapter 0: `NameError: name 'uuid' is not defined`.

**Cambio concreto.** Añadir `import uuid` dentro de `_asegurar_wan` (o a nivel de módulo)
y un test que llame al helper con ese topología mínima, sin depender de `fix`/`import`.

**Criterio de verificación.** La reproducción anterior termina sin excepción, añade un nodo
`nat` (`NAT1`) y un enlace con `port_number` en todas las entradas de `ports_mapping`;
`pytest -q tests/test_cli_lab.py tests/test_exam_cli.py` sigue en exit 0.

### 6. `examen setup` no debe decir «listo» si falla arranque o marca — prioridad media-alta

**Hallazgo.** `cli/gns3lab:3652-3654` descarta el resultado de `project_file_write` del
marker; `cli/gns3lab:3658-3665` imprime un aviso si `nodes_action('start')` falla pero no
cambia el retorno; `cli/gns3lab:3661-3666` acepta estados observados cualquiera y
`cli/gns3lab:3667` imprime `listo` y devuelve `0`. `examen reset` exige esa marca, así que
un setup con marca fallida deja un proyecto que no se puede reiniciar.

**Cambio concreto.** Comprobar el `(st, cuerpo)` de `project_file_write` antes de arrancar y
abortar si falla; tratar `nodes_action` fuera de `(200, 201, 204)` como error; recoger los
estados devueltos por `_wait_node_status` y devolver `1` si alguno no es `started`, con
`ok:false` y el motivo en `--json`.

**Criterio de verificación.** Con arranque HTTP 500 o nodos `stopped`, `examen setup --json`
devuelve `ok:false` y exit distinto de 0, sin «listo»; con la escritura del marker en HTTP
500, no se crea un proyecto utilizable y `reset --yes` lo rechaza. Con arranque correcto,
`examen verify --name … --json` devuelve `ok:true`.

### 7. `pf detect` debe devolver `adapter_type` para que `lab verify` funcione — prioridad media

**Hallazgo.** `cli/gns3lab:4221-4227` construye el JSON de `pf detect` con
`{project, node, wan, lan}` y omite `adapter_type`, aunque la tool MCP sí lo devuelve
(`gns3_mcp_server.py:873-875`). `scripts/labspec.py:533-549` lee exactamente
`data.adapter_type` de ese comando: con cualquier spec que declare `adapter_type`, la
comparación queda `adapter_type=?` y `verify` marca FALLO aunque el nodo sea correcto.

**Cambio concreto.** Añadir `"adapter_type": (node.get("properties") or {}).get("adapter_type")`
al dict `data` de `_pf_detect` (incluido el modo `--json`) y un test con nodo `e1000` y otro
`virtio-net-pci`.

**Criterio de verificación.** `gns3lab pf detect -p P --json` → `data.adapter_type == "e1000"`
para un nodo e1000; `lab verify` con `examples/*.yaml` que declare `adapter_type` pasa esa
comprobación; un valor `virtio-net-pci` se reporta literalmente, sin convertirlo en `?`.

### 8. Reparar el gate `check-links.py` roto por los informes de auditoría — prioridad media

**Hallazgo.** `scripts/check-links.py:21` captura enlaces Markdown y comprueba la ruta tal
cual. Los tres informes `orchestration/auditorias/codex-cli.md`, `codex-core.md` y
`codex-mcp.md` usan enlaces absolutos con número de línea incrustado, p. ej.
`(/home/.../pfsense.py:263)`. `python3 scripts/check-links.py` termina con `ROTO: 23
hallazgos` y exit 1; los 23 son esos enlaces, no código roto.

**Cambio concreto.** Convertir esas referencias a texto plano con backticks
(`pfsense.py:263`) o a enlaces relativos sin el sufijo `:línea`, y añadir una comprobación
en el propio script que ignore las referencias `archivo:linea` dentro de backticks. Este
fichero ya usa esa forma y no introduce nuevos enlaces rotos.

**Criterio de verificación.** `python3 scripts/check-links.py` → exit 0 y `OK: sin enlaces
rotos`; `python3 scripts/verify.py` sigue devolviendo `OK: sin deriva`; el número de
referencias con `fichero:línea` en los informes no baja (se cambia el formato, no la
evidencia).

## Límites

Ninguna recomendación se probó contra un servidor GNS3 o un firewall real. Los comandos
marcados como cambio concreto son propuestas pendientes de implementar; las salidas citadas
son reproducciones con dobles o lectura directa del código en este árbol. No se modificó
código de producción, no se hizo commit ni PR.
