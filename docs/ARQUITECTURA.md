# Arquitectura

Secciones: Tres piezas, un núcleo · Qué hace cada clase de `gns3core.py` · El servidor MCP · Por qué la consola se lee por prompt y no por `sleep` · Por qué el QEMU se maneja por HMP y no por VNC · Flujo de una orden · Estructura plana.

## Tres piezas, un núcleo

```text
                 gns3lab (CLI)                 gns3_mcp_server.py (FastMCP, stdio)
                 cli/gns3lab                   agente / Hermes
                      |                                  |
            argparse + 48 subcomandos           49 tools (@mcp.tool)
                      |                                  |
        +-------------+------------------+---------------+
        |                                |
   (1) Server/Vpcs propios          gns3core
       urllib + socket               Client / Console / QemuMonitor / ocr
        |                                |
        |  HTTP /v2                      |  HTTP /v2  (Client, urllib)
        |  telnet (Vpcs)                 |  telnet    (Console)
        |                                |  TCP local (QemuMonitor, HMP)
        +---------------+----------------+-------------------+
                        |                |                   |
                 servidor GNS3     consola del nodo     proceso QEMU
                 gns3server        (VPCS, IOU, Linux)   (pfSense, OpenWrt)
                 API /v2                  :telnet          -monitor tcp:...
                        |
                 computes: local / GNS3 VM
                 proyectos, nodos, enlaces, imágenes, plantillas
```

Los dos caminos no son simétricos:

- La CLI mantiene su propio `Server` (transporte `urllib`) y su `Vpcs` (consola por socket) para
  los comandos básicos: `servers`, `status`, `up`, `down`, `test`, `export`, `import`, `fix`,
  `port`, `images`, `templates`, `snap`.
- Los comandos nuevos (`exec`, `shot`, `key`, `type`, `mon`, `new`, `node`, `upload`, `draw`,
  `link`, `doctor`) usan `gns3core`. Una corrección de consola, de OCR o de resolución de nodo
  llega a la CLI y al MCP a la vez. `doctor` mezcla: usa `Server` para el servidor y
  `core.find_monitor_port` para los monitores.
- El MCP habla la API con su propio `_api` sobre `httpx` y delega en `gns3core` la consola
  (`core.console_for`), el monitor (`core.QemuMonitor`) y los ficheros de nodo
  (`core.node_file_read/write`).

`gns3core` no importa `fastmcp` ni `httpx`. La CLI funciona con la stdlib; `fastmcp` y `httpx`
sólo existen en el servidor MCP, y `Pillow` es opcional (cae a ImageMagick y, si tampoco está, al
PPM).

## Qué hace cada clase de `gns3core.py`

### `Client`

Cliente mínimo de la API REST `/v2` de GNS3 2.2. Devuelve tuplas `(status, body)` y nunca
imprime.

| Método | Para qué |
|---|---|
| `req/get/post/put/delete` | transporte con Basic auth opcional; `raw=True` para binarios |
| `alive`, `version` | comprobar el servidor |
| `projects`, `nodes`, `links`, `templates`, `qemu_images` | consultas |
| `resolve_project` | proyecto por nombre parcial o id; sin argumento, el único abierto |
| `ensure_open` | abre el proyecto si está cerrado, con un reintento por la carrera de libvirt |
| `find_node`, `node_detail` | nodo por nombre, patrón (`*`, `Router*`, `R[12]`), `node_id` |
| `json_or_die` | GET que lanza si el status no es 200 |

### `Console`

Consola **telnet** de un nodo, leída por prompt o por quietud.

| Método | Para qué |
|---|---|
| `wake` | manda un Enter y devuelve lo que salga |
| `wait_ready` | espera a que haya shell; si aparece `GNU GRUB`, pulsa Enter |
| `run` | ejecuta un comando y devuelve `{cmd, output, ok, ms, timed_out, more_pages}` |
| `run_many` | cadena de comandos compartiendo sesión (`set pcname`, `ip dhcp`, `show ip`) |
| `shell` | alias de `run` cuando no sabes qué prompt esperar |

Durante `run` responde solo a tres cosas: paginación (`--More--`, `(q) quit`), confirmaciones
(`[y/n]`, `are you sure`) y prompts de contraseña (`Password:`). El final de la lectura lo marca
`expect` o la quietud de `idle` segundos.

`console_for(client, pid, node)` es el portero: si el nodo no es telnet, lanza `ConsoleError`
explicando que use el monitor QEMU, en vez de fallar con un socket a un puerto VNC.

### `QemuMonitor` y OCR

Canal HMP del proceso QEMU del nodo.

| Método | Para qué |
|---|---|
| `for_node(node_id, disk)` | encuentra el puerto HMP leyendo `/proc` y el `cmdline` de `qemu-system` |
| `run(cmd)` | comando HMP crudo; devuelve `{cmd, output, error, raw_len}` |
| `sendkey(*keys)` | teclas por nombre HMP (`ret`, `shift-2`, `f2`) |
| `type_text(text)` | traduce carácter a tecla; antes manda `sendkey shift` para despertar |
| `screendump(dest, scale)` | `screendump` de QEMU, conversión a PNG y borrado del PPM |

`key_for` es la tabla de traducción: letras y dígitos van tal cual, mayúsculas como `shift-x`,
símbolos como `shift-2`. `ocr(path, psm)` llama a `tesseract` y devuelve cadena vacía si no está
instalado. `screen_text(monitor)` encadena captura y OCR con `psm 4` y escala 2.

Utilidades sueltas: `match_nodes`, `node_file_read/write` (el body va **en crudo**),
`node_summary`, `local_auth`, `lab_conf`, `server_config`, `clean`.

## El servidor MCP

`gns3_mcp_server.py` es un `FastMCP("gns3")` por stdio. Las credenciales salen de
`~/.config/GNS3/2.2/gns3_server.conf` (`GNS3_URL`, `GNS3_USER`, `GNS3_PASSWORD` como override),
así que no viajan en el prompt. Las 49 tools registradas, contadas con `mcp.list_tools()`:

| Grupo | Tools |
|---|---|
| estado y proyectos | `gns3_status`, `gns3_projects`, `gns3_project_io`, `gns3_project_stats`, `gns3_project_files`, `gns3_project_file_list`, `gns3_informe`, `gns3_verify` |
| topología | `gns3_nodes`, `gns3_nodes_bulk`, `gns3_node_edit`, `gns3_node_action`, `gns3_links`, `gns3_link_get`, `gns3_link_edit`, `gns3_topology`, `gns3_drawings`, `gns3_drawing_get` |
| catálogo y computes | `gns3_templates`, `gns3_template`, `gns3_images`, `gns3_upload`, `gns3_compute`, `gns3_compute_endpoint`, `gns3_compute_download`, `gns3_statistics`, `gns3_symbols`, `gns3_appliances`, `gns3_server_paths`, `gns3_command_line` |
| dentro del nodo | `gns3_console`, `gns3_console_control`, `gns3_exec`, `gns3_monitor`, `gns3_node_files` |
| red, captura y seguridad | `gns3_capture`, `gns3_nio`, `gns3_port_capture`, `gns3_snapshots` |
| admin y eventos | `gns3_gns3vm`, `gns3_iou_license`, `gns3_server`, `gns3_emulator`, `gns3_notifications`, `gns3_events_url`, `gns3_events` |
| pfSense y lotes | `gns3_pfsense`, `gns3_batch` |

Además expone 3 resources (`gns3://status`, `gns3://projects`, `gns3://templates`), un resource
template (`gns3://project/{project}/topology`) y 2 prompts (`gns3-diagnostico`, `gns3-examen`).

`gns3_exec` es la vía preferente sobre `gns3_console`: no espera un tiempo fijo y devuelve la
salida de cada comando por separado. `gns3_console` se mantiene por compatibilidad con la
batería de pruebas.

## Por qué la consola se lee por prompt y no por `sleep`

Un `sleep` fijo falla en las dos direcciones: si es corto, corta la salida a medias; si es largo,
multiplica el tiempo por cada comando. Y hay tres cosas que dejan una sesión telnet colgada y que
un `sleep` no resuelve:

- paginación (`--More--`): el nodo espera una tecla y no manda el resto;
- confirmaciones (`[y/n]`, `are you sure`): el nodo espera una respuesta;
- prompts de contraseña (`Password:`): si no se contesta, no hay shell.

`Console.run` los detecta en la cola de lo recibido y contesta solo. El final se marca con
`expect` o con quietud, así que un comando lento tarda lo que tarde y uno rápido no espera de
más. `wait_ready` añade el caso del disco a medio escribir: si sale `GNU GRUB`, un Enter lo
resuelve.

## Por qué el QEMU se maneja por HMP y no por VNC

El VNC es un protocolo de pantalla: para teclear hace falta un cliente (`vncdotool`, Remmina),
que inyecta eventos en un framebuffer que el invitado puede no estar mirando. En la práctica
pierde y corrompe teclas, y no deja rastro legible de lo que pasó.

El canal HMP (`-monitor tcp`) es el propio QEMU hablando de sí mismo:

- `sendkey` mete la tecla en el dispositivo de entrada de la VM, sin cliente intermedio;
- `screendump` da el framebuffer real, no una copia de la sesión VNC;
- el proceso se identifica por el `node_id` que GNS3 pasa como `-uuid`, así que `for_node` no
  depende de títulos de ventana ni de puertos adivinados.

El precio es que `screendump` escribe un **PPM** aunque el nombre acabe en `.png`: el núcleo lo
convierte con Pillow (o ImageMagick) antes de pasar el OCR. Y el OCR tiene su propio límite: lee
bien 720x400 con fuente VGA 9x16, no texto pequeño. Por eso `shot` usa escala 2 y `psm 4`.

El VNC queda para lo único que no tiene otra vía: instaladores interactivos con ratón.

## Flujo de una orden

`gns3lab exec PC1 "ip dhcp" "show ip" -p examen`:

1. `main()` carga `~/.config/gns3lab/config.json` y resuelve `--server` (global).
2. `cmd_exec` construye `core.Client` con la URL y la auth del servidor.
3. `resolve_project` encuentra `examen`; `ensure_open` lo abre si hace falta.
4. `find_node` localiza `PC1`; `console_for` abre el socket telnet a su puerto.
5. `wait_ready` espera el prompt; `run_many` manda los comandos y lee por prompt/quietud.
6. La CLI imprime; el núcleo no imprime nunca.

`gns3lab shot PF1 -p examen` cambia el paso 4: `QemuMonitor.for_node` busca el puerto HMP en
`/proc`, `screen_text` hace `screendump`, convierte a PNG y llama a `tesseract`.

## Estructura plana

`gns3core.py` y `gns3_mcp_server.py` viven en la raíz. El MCP hace `import gns3core`; la CLI
resuelve el symlink de `~/.local/bin/gns3lab` y añade la raíz a `sys.path`. Un paquete `src/`
no aporta nada aquí y añadiría una capa de rotura justo antes del examen.

En este árbol la suite completa vive en `tests/`: 737 tests recogidos con `pytest --collect-only`
sin servidor. Los dobles de `tests/conftest.py` cubren la API REST falsa, la consola telnet y el
canal HMP. El único fichero que habla con el GNS3 real es `tests/test_mcp_smoke.py`, excluido de
la colección (`collect_ignore`) y ejecutado a mano.
