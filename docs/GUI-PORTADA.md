# De la GUI a la terminal: comando, tool y método del núcleo

Tabla de las operaciones de la GUI operativa portadas a `gns3lab`, al MCP y a `gns3core`.
Los nombres de comando y tool vienen de los contratos de `orchestration/BRIEF-guicli.md` y
`orchestration/BRIEF-guimcp.md`; los métodos y los endpoints se han verificado en
`gns3core.py` (`API_V2_MAP` declara 11 áreas) y el inventario de rutas en
`orchestration/inventario-rutas-gns3.txt`.

**Leyenda**

- **en curso**: nombre acordado en los briefs que todavía **no está** en este árbol. Verificado
  con `gns3lab --help` (30 subcomandos) y `mcp.list_tools()` (26 tools): ninguna de las acciones
  nuevas de la GUI aparece aún. Los carriles `opencode/guicli` y `opencode/guimcp` las están
  añadiendo; cuando se integren, estas celdas dejarán de llevar la marca.
- `†`: el método existe en `Client`, pero hoy no lo consume ningún verbo de CLI ni tool MCP.
- El endpoint es el que llama el método del núcleo, con `/v2` completo. La API v2 del
  controlador es la que opera este repo; la API interna de cada emulador no se expone aquí.

## Resize, consola y proyectos

| Lo que hacías en la GUI | Comando CLI | Tool MCP | Método del núcleo | Endpoint |
|---|---|---|---|---|
| Resize disk (propiedades QEMU) | `gns3lab node disk-resize <nodo> --size <GB> [-p PROY]` (en curso) | `gns3_node_edit(action="disk-resize", size=…)` (en curso) | `node_resize_disk()` † | `POST /v2/projects/{id}/nodes/{nid}/resize_disk` |
| Reset de consola | `gns3lab console reset <nodo>` (en curso) | `gns3_console_control(node, action="reset")` (en curso) | `console_reset()` † | `POST /v2/projects/{id}/nodes/{nid}/console/reset` |
| URL WS de la consola | `gns3lab console url <nodo>` (en curso) | `gns3_console_control(node, action="url")` (en curso) | `console_ws_url()` † | `GET /v2/projects/{id}/nodes/{nid}/console/ws` (la compone desde `node_detail`; no abre el socket) |
| Duplicar proyecto | `gns3lab project duplicate <nombre> [-p PROY]` (en curso) | `gns3_project_io(action="duplicate", …)` (en curso) | `project_duplicate()` † | `POST /v2/projects/{id}/duplicate` |
| Cargar proyecto desde ruta | `gns3lab project load <ruta>` (en curso) | `gns3_project_io(action="load", …)` (en curso) | `project_load()` † | `POST /v2/projects/load` |
| Estadísticas del proyecto | `gns3lab project stats [-p PROY] [--json]` (en curso) | `gns3_project_stats(project_id, project_name)` (en curso) | `project_stats()` † | `GET /v2/projects/{id}/stats` |
| Leer un fichero del proyecto | `gns3lab project file get <ruta>` (en curso) | `gns3_project_files(action="get", path=…)` (en curso) | `project_file_read()` † | `GET /v2/projects/{id}/files/{path}` |
| Escribir un fichero del proyecto | `gns3lab project file put <ruta> [--content TEXTO]` (en curso) | `gns3_project_files(action="put", path=…, content=…)` (en curso) | `project_file_write()` † | `POST /v2/projects/{id}/files/{path}` |

## Computes, GNS3 VM, notificaciones y servidor

| Lo que hacías en la GUI | Comando CLI | Tool MCP | Método del núcleo | Endpoint |
|---|---|---|---|---|
| Listar / ver compute | `gns3lab compute [id]` (parcial: sólo info) | `gns3_compute(cid="local")` (parcial; `action="info\|list"` en curso) | `computes()`, `compute()` † | `GET /v2/computes`, `GET /v2/computes/{id}` |
| Añadir compute | `gns3lab compute add …` (en curso) | `gns3_compute(action="add", …)` (en curso) | `compute_create()` † | `POST /v2/computes` |
| Editar compute | `gns3lab compute update …` (en curso) | `gns3_compute(action="update", …)` (en curso) | `compute_update()` † | `PUT /v2/computes/{id}` |
| Borrar compute | `gns3lab compute rm …` (en curso) | `gns3_compute(action="delete", …)` (en curso) | `compute_delete()` † | `DELETE /v2/computes/{id}` |
| Puertos del compute | `gns3lab compute ports …` (en curso) | `gns3_compute(action="ports", …)` (en curso) | `compute_ports()` † | `GET /v2/computes/{id}/ports` |
| Auto idlepc del compute | `gns3lab compute idlepc …` (en curso) | `gns3_compute(action="idlepc", …)` (en curso) | `compute_auto_idlepc()` † | `POST /v2/computes/{id}/auto_idlepc` |
| Pasarela al compute (img, binaries…) | `gns3lab compute action …` (en curso) | `gns3_compute(action="call", …)` (en curso) | `compute_action()` † | `GET/POST /v2/computes/{id}/{emulator}/{action}` |
| Ver GNS3 VM | `gns3lab gns3vm show` (en curso) | `gns3_gns3vm(action="show")` (en curso) | `gns3vm()` † | `GET /v2/gns3vm` |
| Configurar GNS3 VM | `gns3lab gns3vm set …` (en curso) | `gns3_gns3vm(action="set", body=…)` (en curso) | `gns3vm_update()` † | `PUT /v2/gns3vm` |
| Motores de GNS3 VM | `gns3lab gns3vm engines` (en curso) | `gns3_gns3vm(action="engines")` (en curso) | `gns3vm_engines()` † | `GET /v2/gns3vm/engines` |
| VMs de un motor | `gns3lab gns3vm vms <engine>` (en curso) | `gns3_gns3vm(action="vms", engine=…)` (en curso) | `gns3vm_vms()` † | `GET /v2/gns3vm/engines/{engine}/vms` |
| Notificaciones | `gns3lab notify [proyecto] [--json]` (en curso) | `gns3_notifications(project_id=None, project_name=None)` (en curso) | `notifications()` † | `GET /v2/notifications`, `GET /v2/projects/{id}/notifications` |
| Apagar servidor | `gns3lab server shutdown --yes` (en curso) | `gns3_server(action="shutdown", confirm=True)` (en curso) | `server_shutdown()` † | `POST /v2/shutdown` |
| Recargar servidor | `gns3lab server reload --yes` (en curso) | `gns3_server(action="reload", confirm=True)` (en curso) | `server_reload()` † | `POST /v2/reload` |
| Debug del servidor | `gns3lab server debug --yes` (en curso) | `gns3_server(action="debug", confirm=True)` (en curso) | `server_debug()` † | `POST /v2/debug` |

`gns3_server` contempla además `action="version"`; hoy se sirve con `gns3lab servers` y
`gns3_status`, que leen `GET /v2/version`.

## Plantillas, símbolos y licencia IOU

| Lo que hacías en la GUI | Comando CLI | Tool MCP | Método del núcleo | Endpoint |
|---|---|---|---|---|
| Duplicar plantilla | `gns3lab template duplicate …` (en curso) | `gns3_template(action="duplicate", …)` (en curso) | `template_duplicate()` † | `POST /v2/templates/{id}/duplicate` |
| Listar base-configs | `gns3lab template base-config …` (en curso) | `gns3_template(action="base-config", …)` (en curso) | `template_base_configs()` † | `GET /v2/templates/base-configs` |
| Leer / fijar base-config | `gns3lab template base-config …` (en curso) | `gns3_template(action="base-config", …)` (en curso) | `template_base_config()` † | `GET/PUT /v2/templates/{id}/base-config/{filename}` |
| Listar símbolos | `gns3lab symbols [--filter] [--json]` (existe) | `gns3_symbols(pattern=…)` (existe; `action="list"` en curso) | `symbols()` † | `GET /v2/symbols` |
| Dimensiones de un símbolo | `gns3lab symbol dimensions <id>` (en curso) | `gns3_symbols(action="dimensions", …)` (en curso) | `symbol_dimensions()` † | `GET /v2/symbols/{id}/dimensions` |
| SVG de un símbolo | `gns3lab symbol raw <id>` (en curso) | `gns3_symbols(action="raw", …)` (en curso) | `symbol_raw()` † | `GET /v2/symbols/{id}/raw` |
| Subir SVG de un símbolo | `gns3lab symbol upload <id> …` (en curso) | `gns3_symbols(action="upload", …)` (en curso) | `symbol_raw_upload()` † | `POST /v2/symbols/{id}/raw` |
| Símbolos por defecto | `gns3lab symbol default` (en curso) | `gns3_symbols(action="default")` (en curso) | `default_symbols()` † | `GET /v2/default_symbols` |
| Ver licencia IOU | `gns3lab iou-license get` (en curso) | `gns3_iou_license(action="get")` (en curso) | `iou_license()` † | `GET /v2/iou_license` |
| Fijar licencia IOU | `gns3lab iou-license set …` (en curso) | `gns3_iou_license(action="set", body=…)` (en curso) | `iou_license_update()` † | `PUT /v2/iou_license` |

## Emuladores y diagnosis de nodos/enlaces

| Lo que hacías en la GUI | Comando CLI | Tool MCP | Método del núcleo | Endpoint |
|---|---|---|---|---|
| Binarios QEMU | `gns3lab emulator qemu-binaries` (en curso) | `gns3_emulator(action="qemu-binaries")` (en curso) | `qemu_binaries()` † | `GET /v2/computes/local/qemu/binaries` |
| Capacidades QEMU | `gns3lab emulator qemu-capabilities` (en curso) | `gns3_emulator(action="qemu-capabilities")` (en curso) | `qemu_capabilities()` † | `GET /v2/computes/local/qemu/capabilities` |
| Imágenes Docker | `gns3lab emulator docker-images` (en curso) | `gns3_emulator(action="docker-images")` (en curso) | `docker_images()` † | `GET /v2/computes/local/docker/images` |
| Interfaces de red | `gns3lab emulator interfaces` (en curso) | `gns3_emulator(action="interfaces")` (en curso) | `network_interfaces()` † | `GET /v2/computes/local/network/interfaces` |
| Puertos de red | `gns3lab emulator ports` (en curso) | `gns3_emulator(action="ports")` (en curso) | `network_ports()` † | `GET /v2/computes/local/network/ports` |
| Reservar puerto UDP | `gns3lab emulator udp <puerto>` (en curso) | `gns3_emulator(action="udp", port=…)` (en curso) | `udp_port()` † | `POST /v2/computes/local/ports/udp` |
| Filtros disponibles de un enlace | `gns3lab link filters <link_id> [-p PROY]` (en curso) | `gns3_links(action="filters", …)` (en curso) | `link_available_filters()` † | `GET /v2/projects/{id}/links/{lid}/available_filters` |
| Enlaces de un nodo | `gns3lab node links <nodo> [-p PROY]` (en curso) | `gns3_node_edit(action="links", …)` (en curso) | `node_links()` † | `GET /v2/projects/{id}/nodes/{nid}/links` |
| Idlepc de un nodo | `gns3lab node idlepc <nodo> [-p PROY]` (en curso) | `gns3_node_edit(action="idlepc", …)` (en curso) | `node_idlepc()` † | `GET /v2/projects/{id}/nodes/{nid}/dynamips/auto_idlepc`, `GET …/idlepc_proposals` |

La última ruta (`idlepc_proposals`) está en el handler `dynamips_vm_handler.py`, pero no en
`API_V2_MAP`; `node_idlepc(proposals=True)` la llama igualmente.

## Cómo se ha verificado

```bash
grep -c '^@mcp.tool' gns3_mcp_server.py                 # 26
./cli/gns3lab --help | head -1 | tr ',' '\n' | wc -l   # 30
python3 - <<'PY'                                          # 11 áreas en API_V2_MAP
import ast, re
s = open('gns3core.py').read()
d = ast.literal_eval(re.search(r'API_V2_MAP[^=]*= (\{.*?\n\})', s, re.S).group(1))
print(len(d), list(d))
PY
grep -n 'def node_resize_disk\|def console_reset\|def gns3vm\|def symbols' gns3core.py
```

Ejecutados en este árbol: `mcp.list_tools()` devuelve 26 tools y `gns3lab --help` lista 30
subcomandos; las acciones de los dos briefs aún no figuran en ninguna de las dos listas. Los
métodos del núcleo y los endpoints sí figuran en `gns3core.py`.

Matriz endpoint a endpoint en [API-COVERAGE.md](API-COVERAGE.md); límites de versión en
[COMPATIBILIDAD.md](COMPATIBILIDAD.md); referencia de comandos existentes en
[COMANDOS.md](COMANDOS.md) y paridad CLI/MCP en [PARIDAD.md](PARIDAD.md).
