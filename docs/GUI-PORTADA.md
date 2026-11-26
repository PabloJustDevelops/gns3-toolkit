# De la GUI a la terminal: comando, tool y método del núcleo

Secciones: Resize, consola y proyectos · Computes, GNS3 VM, notificaciones y servidor · Plantillas, símbolos y licencia IOU · Emuladores y diagnosis de nodos/enlaces · NIO, capturas por puerto, acciones masivas y eventos · Cómo se ha verificado.

Tabla de las operaciones de la GUI operativa portadas a `gns3lab`, al MCP y a `gns3core`.
Los nombres de comando y tool están verificados en `cli/gns3lab` y `gns3_mcp_server.py`; los
métodos y los endpoints, en `gns3core.py` (`API_V2_MAP` declara 12 áreas), y el inventario de
rutas en `orchestration/inventario-rutas-gns3.txt`.

**Leyenda**

- `†`: el método existe en `Client` y es consumido por el verbo/tool indicado en la misma fila.
- Todas las operaciones de las tablas están integradas en el árbol actual. Los números se
  recuentan desde el código (`gns3lab --help` y `mcp.list_tools()`), nunca se copian.
- El endpoint es el que llama el método del núcleo, con `/v2` completo. La API v2 del
  controlador es la que opera este repo; la API interna de cada emulador no se expone aquí.

## Resize, consola y proyectos

| Lo que hacías en la GUI | Comando CLI | Tool MCP | Método del núcleo | Endpoint |
|---|---|---|---|---|
| Resize disk (propiedades QEMU) | `gns3lab node disk-resize <nodo> --size <GB> [-p PROY]` | `gns3_node_edit(action="disk-resize", size=…)` | `node_resize_disk()` † | `POST /v2/projects/{id}/nodes/{nid}/resize_disk` |
| Reset de consola | `gns3lab console reset <nodo>` | `gns3_console_control(node, action="reset")` | `console_reset()` † | `POST /v2/projects/{id}/nodes/{nid}/console/reset` |
| URL WS de la consola | `gns3lab console url <nodo>` | `gns3_console_control(node, action="url")` | `console_ws_url()` † | `GET /v2/projects/{id}/nodes/{nid}/console/ws` (la compone desde `node_detail`; no abre el socket) |
| Duplicar proyecto | `gns3lab project duplicate <nombre> [-p PROY]` | `gns3_project_io(action="duplicate", …)` | `project_duplicate()` † | `POST /v2/projects/{id}/duplicate` |
| Cargar proyecto desde ruta | `gns3lab project load <ruta>` | `gns3_project_io(action="load", …)` | `project_load()` † | `POST /v2/projects/load` |
| Estadísticas del proyecto | `gns3lab project stats [-p PROY] [--json]` | `gns3_project_stats(project_id, project_name)` | `project_stats()` † | `GET /v2/projects/{id}/stats` |
| Leer un fichero del proyecto | `gns3lab project file get <ruta>` | `gns3_project_files(action="get", path=…)` | `project_file_read()` † | `GET /v2/projects/{id}/files/{path}` |
| Escribir un fichero del proyecto | `gns3lab project file put <ruta> [--content TEXTO]` | `gns3_project_files(action="put", path=…, content=…)` | `project_file_write()` † | `POST /v2/projects/{id}/files/{path}` |

## Computes, GNS3 VM, notificaciones y servidor

| Lo que hacías en la GUI | Comando CLI | Tool MCP | Método del núcleo | Endpoint |
|---|---|---|---|---|
| Listar / ver compute | `gns3lab compute [id]` (parcial: sólo info) | `gns3_compute(action="info\|list")` | `computes()`, `compute()` † | `GET /v2/computes`, `GET /v2/computes/{id}` |
| Añadir compute | `gns3lab compute add …` | `gns3_compute(action="add", …)` | `compute_create()` † | `POST /v2/computes` |
| Editar compute | `gns3lab compute update …` | `gns3_compute(action="update", …)` | `compute_update()` † | `PUT /v2/computes/{id}` |
| Borrar compute | `gns3lab compute rm …` | `gns3_compute(action="delete", …)` | `compute_delete()` † | `DELETE /v2/computes/{id}` |
| Puertos del compute | `gns3lab compute ports …` | `gns3_compute(action="ports", …)` | `compute_ports()` † | `GET /v2/computes/{id}/ports` |
| Auto idlepc del compute | `gns3lab compute idlepc …` | `gns3_compute(action="idlepc", …)` | `compute_auto_idlepc()` † | `POST /v2/computes/{id}/auto_idlepc` |
| Pasarela al compute (img, binaries…) | `gns3lab compute action …` | `gns3_compute(action="call", …)` | `compute_action()` † | `GET/POST /v2/computes/{id}/{emulator}/{action}` |
| Ver GNS3 VM | `gns3lab gns3vm show` | `gns3_gns3vm(action="show")` | `gns3vm()` † | `GET /v2/gns3vm` |
| Configurar GNS3 VM | `gns3lab gns3vm set …` | `gns3_gns3vm(action="set", body=…)` | `gns3vm_update()` † | `PUT /v2/gns3vm` |
| Motores de GNS3 VM | `gns3lab gns3vm engines` | `gns3_gns3vm(action="engines")` | `gns3vm_engines()` † | `GET /v2/gns3vm/engines` |
| VMs de un motor | `gns3lab gns3vm vms <engine>` | `gns3_gns3vm(action="vms", engine=…)` | `gns3vm_vms()` † | `GET /v2/gns3vm/engines/{engine}/vms` |
| Notificaciones | `gns3lab notify [proyecto] [--json]` | `gns3_notifications(project_id=None, project_name=None)` | `notifications()` † | `GET /v2/notifications`, `GET /v2/projects/{id}/notifications` |
| Apagar servidor | `gns3lab server shutdown --yes` | `gns3_server(action="shutdown", confirm=True)` | `server_shutdown()` † | `POST /v2/shutdown` |
| Recargar servidor | `gns3lab server reload --yes` | `gns3_server(action="reload", confirm=True)` | `server_reload()` † | `POST /v2/reload` |
| Debug del servidor | `gns3lab server debug --yes` | `gns3_server(action="debug", confirm=True)` | `server_debug()` † | `POST /v2/debug` |

`gns3_server` contempla además `action="version"`; hoy se sirve con `gns3lab servers` y
`gns3_status`, que leen `GET /v2/version`.

## Plantillas, símbolos y licencia IOU

| Lo que hacías en la GUI | Comando CLI | Tool MCP | Método del núcleo | Endpoint |
|---|---|---|---|---|
| Duplicar plantilla | `gns3lab template duplicate …` | `gns3_template(action="duplicate", …)` | `template_duplicate()` † | `POST /v2/templates/{id}/duplicate` |
| Listar base-configs | `gns3lab template base-config …` | `gns3_template(action="base-config", …)` | `template_base_configs()` † | `GET /v2/templates/base-configs` |
| Leer / fijar base-config | `gns3lab template base-config …` | `gns3_template(action="base-config", …)` | `template_base_config()` † | `GET/PUT /v2/templates/{id}/base-config/{filename}` |
| Listar símbolos | `gns3lab symbols [--filter] [--json]` (existe) | `gns3_symbols(pattern=…)` | `symbols()` † | `GET /v2/symbols` |
| Dimensiones de un símbolo | `gns3lab symbol dimensions <id>` | `gns3_symbols(action="dimensions", …)` | `symbol_dimensions()` † | `GET /v2/symbols/{id}/dimensions` |
| SVG de un símbolo | `gns3lab symbol raw <id>` | `gns3_symbols(action="raw", …)` | `symbol_raw()` † | `GET /v2/symbols/{id}/raw` |
| Subir SVG de un símbolo | `gns3lab symbol upload <id> …` | `gns3_symbols(action="upload", …)` | `symbol_raw_upload()` † | `POST /v2/symbols/{id}/raw` |
| Símbolos por defecto | `gns3lab symbol default` | `gns3_symbols(action="default")` | `default_symbols()` † | `GET /v2/default_symbols` |
| Ver licencia IOU | `gns3lab iou-license get` | `gns3_iou_license(action="get")` | `iou_license()` † | `GET /v2/iou_license` |
| Fijar licencia IOU | `gns3lab iou-license set …` | `gns3_iou_license(action="set", body=…)` | `iou_license_update()` † | `PUT /v2/iou_license` |

## Emuladores y diagnosis de nodos/enlaces

| Lo que hacías en la GUI | Comando CLI | Tool MCP | Método del núcleo | Endpoint |
|---|---|---|---|---|
| Binarios QEMU | `gns3lab emulator qemu-binaries` | `gns3_emulator(action="qemu-binaries")` | `qemu_binaries()` † | `GET /v2/computes/local/qemu/binaries` |
| Capacidades QEMU | `gns3lab emulator qemu-capabilities` | `gns3_emulator(action="qemu-capabilities")` | `qemu_capabilities()` † | `GET /v2/computes/local/qemu/capabilities` |
| Imágenes Docker | `gns3lab emulator docker-images` | `gns3_emulator(action="docker-images")` | `docker_images()` † | `GET /v2/computes/local/docker/images` |
| Interfaces de red | `gns3lab emulator interfaces` | `gns3_emulator(action="interfaces")` | `network_interfaces()` † | `GET /v2/computes/local/network/interfaces` |
| Puertos de red | `gns3lab emulator ports` | `gns3_emulator(action="ports")` | `network_ports()` † | `GET /v2/computes/local/network/ports` |
| Reservar puerto UDP | `gns3lab emulator udp <puerto>` | `gns3_emulator(action="udp", port=…)` | `udp_port()` † | `POST /v2/computes/local/ports/udp` |
| Filtros disponibles de un enlace | `gns3lab link filters <link_id> [-p PROY]` | `gns3_links(action="filters", …)` | `link_available_filters()` † | `GET /v2/projects/{id}/links/{lid}/available_filters` |
| Enlaces de un nodo | `gns3lab node links <nodo> [-p PROY]` | `gns3_node_edit(action="links", …)` | `node_links()` † | `GET /v2/projects/{id}/nodes/{nid}/links` |
| Idlepc de un nodo | `gns3lab node idlepc <nodo> [-p PROY]` | `gns3_node_edit(action="idlepc", …)` | `node_idlepc()` † | `GET /v2/projects/{id}/nodes/{nid}/dynamips/auto_idlepc`, `GET …/idlepc_proposals` |

La última ruta (`idlepc_proposals`) está en el handler `dynamips_vm_handler.py`, pero no en
`API_V2_MAP`; `node_idlepc(proposals=True)` la llama igualmente.

## NIO, capturas por puerto, acciones masivas y eventos

| Lo que hacías en la GUI | Comando CLI | Tool MCP | Método del núcleo | Endpoint |
|---|---|---|---|---|
| Ver el NIO de un puerto | `gns3lab nio get <nodo> --adapter N --port N` | `gns3_nio(action="get", …)` | `port_nio()` † | `GET /v2/computes/local/projects/{id}/{emu}/nodes/{nid}/adapters/{a}/ports/{p}/nio` |
| Fijar/borrar el NIO | `gns3lab nio add\|rm <nodo> --adapter N --port N [--nio JSON]` | `gns3_nio(action="set\|delete", …)` | `port_nio()` † | `PUT/DELETE /computes/local/projects/{id}/{emu}/nodes/{nid}/adapters/{a}/ports/{p}/nio` |
| Capturar un puerto | `gns3lab capture-port <nodo> start\|stop\|pcap --adapter N --port N` | `gns3_port_capture(action="start\|stop\|pcap", …)` | `port_capture()` † | `POST /computes/local/…/ports/{p}/{start_capture\|stop_capture}`, `GET …/pcap` |
| Arrancar/parar toda la topología | `gns3lab all start\|stop\|suspend\|reload --yes` | `gns3_nodes_bulk(…, confirm=True)` | `nodes_action()` † | `POST /v2/projects/{id}/nodes/{start\|stop\|suspend\|reload}` |
| Reanudar/pausar un nodo | `gns3lab node resume\|pause\|unpause <nodo>` | `gns3_node_action(action="resume\|pause\|unpause")` | `node_action()` † | `POST /v2/projects/{id}/nodes/{nid}/{resume\|pause\|unpause}` |
| Reset de todas las consolas | `gns3lab console reset-all --yes` | `gns3_console_control(action="reset-all", confirm=True)` | `nodes_console_reset()` † | `POST /v2/projects/{id}/nodes/console/reset` |
| Binarios y configuración qemu-img | `gns3lab disk binaries\|config [--set clave=valor]` | `gns3_emulator(action="img-binaries\|img-config")` | `qemu_img_binaries()`, `qemu_img_config()` † | `GET /v2/computes/local/qemu/img-binaries`, `POST/PUT …/qemu/img` |
| VMs invitadas (VirtualBox/VMware) | `gns3lab vm vms\|vmnet [--set clave=valor]` | `gns3_emulator(action="virtualbox-vms\|vmware-vms\|vmware-vmnet")` | `virtualbox_vms()`, `vmware_vms()`, `vmware_vmnet()` † | `GET /v2/computes/local/{virtualbox\|vmware}/vms`, `POST …/vmware/nodes/interfaces/vmnet` |
| Ver eventos en vivo | `gns3lab watch [--project] [--seconds N]` | `gns3_events_url(...)`, `gns3_events(action="url\|listen")` | `notifications_ws_url()` † | `GET /v2/notifications/ws`, `GET /v2/projects/{id}/notifications/ws` |
| Versión v1 | `gns3lab version-v1` | `gns3_status` con `version_v1` | `v1_version()` † | `GET /v1/version` |

`nio` y `capture-port` pasan por el compute local; un `500` se muestra con su mensaje literal,
sin disfrazarlo. Los verbos reales, el body del NIO y el significado del `500` están en
[NIO-Y-CAPTURAS.md](NIO-Y-CAPTURAS.md); los eventos y su formato en [EVENTOS.md](EVENTOS.md).

## Cómo se ha verificado

```bash
grep -c '^@mcp.tool' gns3_mcp_server.py                          # 43
./cli/gns3lab --help | sed -n '2p' | tr -d ' ' | tr ',' '\n' | wc -l  # 47
python3 - <<'PY'                                                  # 12 áreas en API_V2_MAP
import ast, re
s = open('gns3core.py').read()
d = ast.literal_eval(re.search(r'API_V2_MAP[^=]*= (\{.*?\n\})', s, re.S).group(1))
print(len(d), list(d))
PY
grep -n 'def node_resize_disk\|def console_reset\|def gns3vm\|def symbols' gns3core.py
```

Verificado en este árbol: `mcp.list_tools()` devuelve 43 tools y `gns3lab` registra 47
subcomandos. Las operaciones de la última tabla (NIO, captura por puerto, acciones masivas,
eventos WS y versión v1) figuran en ambas listas; los métodos del núcleo y los endpoints están
en `gns3core.py` y en el inventario de rutas.

Matriz endpoint a endpoint en [API-COVERAGE.md](API-COVERAGE.md); límites de versión en
[COMPATIBILIDAD.md](COMPATIBILIDAD.md); referencia de comandos existentes en
[COMANDOS.md](COMANDOS.md) y paridad CLI/MCP en [PARIDAD.md](PARIDAD.md).
