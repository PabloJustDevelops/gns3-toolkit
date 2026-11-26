# Cobertura de la API v2

Secciones: Cómo se verificó · `server` · `computes` · `projects` · `templates` · `nodes` · `links` · `drawings` · `snapshots` · `symbols` · `gui_admin` · `emulators` · `nio_ports` · Rutas del inventario sin método en el núcleo.

`gns3core.API_V2_MAP` declara **12 áreas**: `server`, `computes`, `projects`, `templates`,
`nodes`, `links`, `drawings`, `snapshots`, `symbols`, `gui_admin`, `emulators` y `nio_ports`.
Este documento dice qué método del núcleo cubre cada endpoint, qué verbo de `gns3lab` y qué
acción MCP lo consumen, y qué test lo prueba.

Fuente de verdad: `gns3core.py` (`API_V2_MAP` y las firmas de `Client`), `cli/gns3lab` (dict
`handlers` y handlers) y `gns3_mcp_server.py` (funciones `@mcp.tool`). Las cifras se recuentan
con `python3 scripts/verify.py`; no se copian de memoria.

## Cómo se verificó

Servidor GNS3 2.2.61 en `http://127.0.0.1:3080`. Sólo `GET` de lectura: `200` es ruta viva;
`405` o `403`, ruta viva con otro método; `409`, estado esperado (captura parada, proyecto
abierto); timeout, descarga o stream en curso. El inventario se contrastó con
`gns3server/handlers/api/` de la instalación local.

Leyenda: `—` no existe en ese lado. `URL` significa que el núcleo compone la dirección pero no
abre el canal.

## Verificación por componente

`gns3lab verify` y `gns3_verify` no añaden rutas: reutilizan `GET /v2/projects` (`resolve_project`),
`GET /v2/projects/{id}/nodes` (`nodes`) y, según el componente, `/proc` (puerto HMP), el canal
HMP (`info status`), la consola telnet (`show ip`) o `pfsense.PfSense.get_config()`
(`cat /conf/config.xml`). Nunca abren el proyecto ni escriben en el firewall. Contrato y límites
en [VERIFICACION.md](VERIFICACION.md); pruebas en `tests/test_verify_component.py`.

## `server`

| Endpoint | Método de `gns3core` | CLI | MCP | Test |
|---|---|---|---|---|
| `GET /v2/version` | `version()`, `alive()` | `servers`, `status`, `doctor` | `gns3_status` | `test_client_v2.py::test_version_devuelve_el_dict` |
| `GET /v1/version` | `v1_version()` | `version-v1` | `gns3_status` (`version_v1`) | `test_client_nio.py::test_consultas_ampliadas_de_compute_y_version` |

## `computes`

| Endpoint | Método de `gns3core` | CLI | MCP | Test |
|---|---|---|---|---|
| `GET /v2/computes` | `computes()` | `compute`, `doctor` | `gns3_compute` (list), `gns3_status` | `test_client_v2.py::test_computes_estadisticas_simbolos_y_appliances` |
| `POST /v2/computes` | `compute_create()` | `compute add` | `gns3_compute` (add) | `test_client_gui.py` |
| `GET/PUT/DELETE /v2/computes/{id}` | `compute()`, `compute_update()`, `compute_delete()` | `compute [id]`, `compute update`, `compute rm` | `gns3_compute` (info/update/delete) | `test_client_v2.py::test_compute_devuelve_dict_o_none` |
| `GET /v2/computes/{id}/ports` | `compute_ports()` | `compute ports` | `gns3_compute` (ports) | `test_client_gui.py` |
| `POST /v2/computes/{id}/auto_idlepc` | `compute_auto_idlepc()` | `compute idlepc` | `gns3_compute` (idlepc) | `test_client_gui.py` |
| `GET /v2/computes/{id}/{emulator}/{action}` | `compute_action()` (GET sin body, POST con body) | `compute action` | `gns3_compute` (call) | `test_client_nio.py::test_consultas_ampliadas_de_compute_y_version` |
| `GET /v2/statistics` | `statistics()` | `stats` | `gns3_statistics` | `test_client_v2.py::test_computes_estadisticas_simbolos_y_appliances` |
| `GET /v2/computes/{id}/{emulator}/images` | `images()`, `qemu_images()` | `images` | `gns3_images` | `test_client_v2.py::test_images_acepta_el_sufijo_images` |
| `POST /v2/computes/{id}/{emulator}/images/{filename}` | `compute_write_file()` | `upload` | `gns3_upload` | `test_client_v2.py::test_compute_write_file_manda_los_bytes_tal_cual` |

## `projects`

| Endpoint | Método de `gns3core` | CLI | MCP | Test |
|---|---|---|---|---|
| `GET/POST /v2/projects` | `projects()`; `POST` en crudo | `status`; `new` | `gns3_projects` (list/create) | `test_client.py::test_projects_devuelve_la_lista` |
| `GET/PUT/DELETE /v2/projects/{id}` | `project_get()`, `project_close()`, `project_delete()`; `PUT` en crudo | `status`, `import`, `port` | `gns3_projects` (info/update/delete) | `test_client_v2.py::test_project_get_y_errores` |
| `POST /v2/projects/{id}/open` | `ensure_open()` | `up`, `new`, `port` | `_ensure_open()` en las tools | `test_client_v2.py::test_ensure_open_abre_el_proyecto` |
| `POST /v2/projects/{id}/close` | `project_close()` | `down` | `gns3_projects` (close) | `test_client_v2.py::test_project_close_y_delete` |
| `GET /v2/projects/{id}/export` | GET crudo con `raw=True` | `export`, `port` | `gns3_project_io` (export) | `test_client_v2.py` |
| `POST /v2/projects/{id}/import` | POST crudo | `import`, `port` | `gns3_project_io` (import) | `test_client_v2.py` |
| `POST /v2/projects/{id}/duplicate` | `project_duplicate()` | `project duplicate` | `gns3_project_io` (duplicate) | `test_client_gui.py` |
| `POST /v2/projects/load` | `project_load()` | `project load` | `gns3_project_io` (load) | `test_client_gui.py` |
| `GET /v2/projects/{id}/stats` | `project_stats()` | `project stats` | `gns3_project_stats` | `test_client_gui.py` |
| `GET/POST /v2/projects/{id}/files/{path}` | `project_file_read()`, `project_file_write()` | `project file` | `gns3_project_files` | `test_client_gui.py` |

## `templates`

| Endpoint | Método de `gns3core` | CLI | MCP | Test |
|---|---|---|---|---|
| `GET /v2/templates` | `templates()` | `templates`, `template list`, `node add` | `gns3_templates`, `gns3_template` (list) | `test_client_v2.py::test_links_templates_y_qemu_images` |
| `GET/PUT/DELETE /v2/templates/{id}` | `template_get/update/delete()` | `template update|delete` | `gns3_template` (update/delete) | `test_client_v2.py::test_template_get_update_delete` |
| `POST /v2/templates` | POST crudo | `template create` | `gns3_template` (create) | `test_client_gui.py` |
| `POST /v2/projects/{id}/templates/{tid}` | POST crudo | `node add` | `gns3_nodes` (add), `gns3_template` (apply) | `test_client.py::test_nodes_pide_el_proyecto_correcto` |
| `POST /v2/templates/{id}/duplicate` | `template_duplicate()` | `template duplicate` | `gns3_template` (duplicate) | `test_client_gui.py` |
| `GET /v2/templates/base-configs` | `template_base_configs()` | `template base-config` | `gns3_template` (base-config) | `test_client_gui.py` |
| `GET/PUT /v2/templates/{id}/base-config/{filename}` | `template_base_config()` | `template base-config` | `gns3_template` (base-config) | `test_client_gui.py` |
| `GET /v2/appliances` | `appliances()` | `appliances` | `gns3_appliances` | `test_client_v2.py::test_computes_estadisticas_simbolos_y_appliances` |

## `nodes`

| Endpoint | Método de `gns3core` | CLI | MCP | Test |
|---|---|---|---|---|
| `GET/POST /v2/projects/{id}/nodes` | `nodes()`; `POST` en crudo | `status`; `node add` | `gns3_nodes` (list/add), `gns3_node_edit` (create) | `test_client.py::test_nodes_pide_el_proyecto_correcto` |
| `GET/PUT/DELETE /v2/projects/{id}/nodes/{nid}` | `node_detail()`, `find_node()`; `PUT`/`DELETE` en crudo | `node props`, `node switch`, `node disk`, `node rm` | `gns3_node_edit`, `gns3_nodes` (delete) | `test_client_v2.py::test_consultas_de_nodo_propagan_http_no_200` |
| `POST /v2/projects/{id}/nodes/{nid}/{start|stop|reload|suspend|resume|pause|unpause}` | `node_action()` | `node start`, `node pause`… | `gns3_node_action`, `gns3_nodes` | `test_client_v2.py::test_node_action_valida_manda_el_post` |
| `POST /v2/projects/{id}/nodes/{start|stop|suspend|reload}` | `nodes_action()` | `all start|stop|suspend|reload` | `gns3_nodes_bulk` | `test_client_nio.py::test_nodes_action_manda_las_cuatro_acciones` |
| `POST /v2/projects/{id}/nodes/console/reset` | `nodes_console_reset()` | `console reset-all` | `gns3_console_control` (reset-all) | `test_client_nio.py::test_nodes_console_reset_manda_el_post` |
| `POST /v2/projects/{id}/nodes/{nid}/duplicate` | POST crudo | `node dup` | `gns3_node_edit` (duplicate) | `test_client_gui.py` |
| `GET/POST /v2/projects/{id}/nodes/{nid}/files/{path}` | `node_file_read()`, `node_file_write()` | — | `gns3_node_files` | `test_files.py` |
| `GET /v2/projects/{id}/nodes/{nid}/links` | `node_links()` | `node links` | `gns3_node_edit` (links) | `test_client_gui.py` |
| `POST /v2/projects/{id}/nodes/{nid}/resize_disk` | `node_resize_disk()` | `node disk-resize` | `gns3_node_edit` (disk-resize) | `test_client_gui.py` |
| `POST /v2/projects/{id}/nodes/{nid}/console/reset` | `console_reset()` | `console reset` | `gns3_console_control` (reset) | `test_client_gui.py` |
| `GET /v2/projects/{id}/nodes/{nid}/console/ws` | `console_ws_url()` (URL) | `console url` | `gns3_console_control` (url) | `test_client_gui.py` |
| sin ruta propia: `GET /v2/projects/{id}/nodes/{nid}` y campo `command_line` | `node_command_line()` | `node line` | `gns3_command_line` | `test_client_v2.py::test_node_command_line_lee_el_detalle` |
| `GET /v2/projects/{id}/nodes/{nid}/dynamips/auto_idlepc` | `node_idlepc()` | `node idlepc` | `gns3_node_edit` (idlepc) | `test_client_gui.py` |
| `GET /v2/symbols` | `symbols()` | `symbols` | `gns3_symbols` (list) | `test_client_v2.py::test_computes_estadisticas_simbolos_y_appliances` |

## `links`

| Endpoint | Método de `gns3core` | CLI | MCP | Test |
|---|---|---|---|---|
| `GET/POST /v2/projects/{id}/links` | `links()`; `POST` en crudo | `link list`, `link add` | `gns3_links`, `gns3_link_edit` | `test_client_v2.py::test_links_templates_y_qemu_images` |
| `GET/PUT/DELETE /v2/projects/{id}/links/{lid}` | `link_update()`, `link_delete()` | `link edit`, `link rm` | `gns3_links` (update/delete), `gns3_link_edit` | `test_client_v2.py::test_link_update_y_delete` |
| `GET /v2/projects/{id}/links/{lid}/available_filters` | `link_available_filters()` | `link filters` | `gns3_links` (filters) | `test_client_gui.py` |
| `POST /v2/projects/{id}/links/{lid}/{start_capture|stop_capture}` | `link_capture()` | `capture … start|stop` | `gns3_capture` | `test_client_v2.py::test_link_capture_start_usa_el_nombre_por_defecto` |
| `GET /v2/projects/{id}/links/{lid}/pcap` | `link_capture(action="pcap")` | `capture … pcap` | `gns3_capture` (read) | `test_client_v2.py::test_link_capture_stop_y_pcap` |

## `drawings`

| Endpoint | Método de `gns3core` | CLI | MCP | Test |
|---|---|---|---|---|
| `GET/POST /v2/projects/{id}/drawings` | `drawings()`, `drawing_create()` | `draw`, `draw list` | `gns3_drawings` (list/text/rect) | `test_client_v2.py::test_drawings_y_drawing_create` |
| `GET/PUT/DELETE /v2/projects/{id}/drawings/{did}` | `drawing_update()`, `drawing_delete()` | `draw edit`, `draw rm` | `gns3_drawings` (update/delete/clear) | `test_client_v2.py::test_drawing_update_y_delete` |

## `snapshots`

| Endpoint | Método de `gns3core` | CLI | MCP | Test |
|---|---|---|---|---|
| `GET/POST /v2/projects/{id}/snapshots` | `snapshots()`, `snapshot_create()` | `snap list`, `snap create` | `gns3_snapshots` (list/create) | `test_client_v2.py::test_snapshots_y_acciones` |
| `POST /v2/projects/{id}/snapshots/{sid}/restore` | `snapshot_restore()` | `snap restore` | `gns3_snapshots` (restore) | `test_client_v2.py::test_snapshots_y_acciones` |
| `DELETE /v2/projects/{id}/snapshots/{sid}` | `snapshot_delete()` | `snap delete` | `gns3_snapshots` (delete) | `test_client_v2.py::test_snapshots_y_acciones` |

## `symbols`

| Endpoint | Método de `gns3core` | CLI | MCP | Test |
|---|---|---|---|---|
| `GET /v2/symbols` | `symbols()` | `symbols` | `gns3_symbols` (list) | `test_client_v2.py::test_computes_estadisticas_simbolos_y_appliances` |
| `GET /v2/symbols/{id}/dimensions` | `symbol_dimensions()` | `symbol dimensions` | `gns3_symbols` (dimensions) | `test_client_gui.py` |
| `GET/POST /v2/symbols/{id}/raw` | `symbol_raw()`, `symbol_raw_upload()` | `symbol raw`, `symbol upload` | `gns3_symbols` (raw/upload) | `test_client_gui.py` |
| `GET /v2/default_symbols` | `default_symbols()` | `symbol default` | `gns3_symbols` (default) | `test_client_gui.py` |

## `gui_admin`

| Endpoint | Método de `gns3core` | CLI | MCP | Test |
|---|---|---|---|---|
| `GET/PUT /v2/gns3vm` | `gns3vm()`, `gns3vm_update()` | `gns3vm show|set` | `gns3_gns3vm` (show/set) | `test_client_gui.py` |
| `GET /v2/gns3vm/engines`, `/engines/{e}/vms` | `gns3vm_engines()`, `gns3vm_vms()` | `gns3vm engines|vms` | `gns3_gns3vm` (engines/vms) | `test_client_gui.py` |
| `GET/PUT /v2/iou_license` | `iou_license()`, `iou_license_update()` | `iou-license get|set` | `gns3_iou_license` | `test_client_gui.py` |
| `GET /v2/notifications`, `/v2/projects/{id}/notifications` | `notifications()` | `notify` | `gns3_notifications` | `test_client_gui.py` |
| `POST /v2/shutdown`, `/reload`, `/debug` | `server_shutdown()`, `server_reload()`, `server_debug()` | `server shutdown|reload|debug --yes` | `gns3_server` (`confirm=True`) | `test_client_gui.py` |

## `emulators`

| Endpoint | Método de `gns3core` | CLI | MCP | Test |
|---|---|---|---|---|
| `GET /v2/computes/local/qemu/binaries` | `qemu_binaries()` | `emulator qemu-binaries` | `gns3_emulator` (qemu-binaries) | `test_client_gui.py` |
| `GET /v2/computes/local/qemu/capabilities` | `qemu_capabilities()` | `emulator qemu-capabilities` | `gns3_emulator` (qemu-capabilities) | `test_client_gui.py` |
| `GET /v2/computes/local/docker/images` | `docker_images()` | `emulator docker-images` | `gns3_emulator` (docker-images) | `test_client_gui.py` |
| `GET /v2/computes/local/network/interfaces` | `network_interfaces()` | `emulator interfaces` | `gns3_emulator` (interfaces) | `test_client_gui.py` |
| `GET /v2/computes/local/network/ports` | `network_ports()` | `emulator ports` | `gns3_emulator` (ports) | `test_client_gui.py` |
| `POST /v2/computes/local/ports/udp` | `udp_port()` | `emulator udp --port N` | `gns3_emulator` (udp) | `test_client_gui.py` |
| `GET /v2/computes/local/qemu/img-binaries`, `POST/PUT .../qemu/img` | `qemu_img_binaries()`, `qemu_img_config()` | `disk binaries|config` | `gns3_emulator` (img-binaries/img-config) | `test_client_nio.py::test_qemu_img_config_con_y_sin_body` |
| `GET /v2/computes/local/{virtualbox|vmware}/vms`, `POST .../vmware/nodes/interfaces/vmnet` | `virtualbox_vms()`, `vmware_vms()`, `vmware_vmnet()` | `vm vms|vmnet` | `gns3_emulator` (virtualbox-vms/vmware-vms/vmware-vmnet) | `test_client_nio.py::test_vmware_vmnet_con_y_sin_body` |

## `nio_ports`

| Endpoint | Método de `gns3core` | CLI | MCP | Test |
|---|---|---|---|---|
| `GET/PUT/DELETE /v2/computes/local/projects/{id}/{emu}/nodes/{nid}/adapters/{a}/ports/{p}/nio` | `port_nio()`, `_emulator_for()` | `nio get|add|rm` | `gns3_nio` (get/set/delete) | `test_client_nio.py::test_port_nio_cubre_metodos_y_emulador` |
| `POST /…/ports/{p}/start_capture`, `stop_capture` | `port_capture()` | `capture-port … start|stop` | `gns3_port_capture` | `test_client_nio.py::test_port_capture_start_y_stop_mandan_el_body_exacto` |
| `GET /…/ports/{p}/pcap` | `port_capture(action="pcap")` | `capture-port … pcap` | `gns3_port_capture` (pcap) | `test_client_nio.py::test_port_capture_pcap_devuelve_los_bytes_en_crudo` |
| `GET /v2/notifications/ws`, `/v2/projects/{id}/notifications/ws` | `notifications_ws_url()` (URL) | `watch` | `gns3_events_url`, `gns3_events` | `test_client_nio.py::test_notifications_ws_url_con_y_sin_proyecto` |
| `GET /v1/version` | `v1_version()` | `version-v1` | `gns3_status` (version_v1) | `test_client_nio.py::test_consultas_ampliadas_de_compute_y_version` |

Las acciones masivas, `reset-all` y los cambios de configuración son disruptivos: la CLI exige
`--yes` o TTY y el MCP `confirm=True`. Las escrituras contra el servidor real no se sondean en
este documento: iniciar una captura o cambiar un NIO modifica el laboratorio. Detalle en
[NIO-Y-CAPTURAS.md](NIO-Y-CAPTURAS.md) y [EVENTOS.md](EVENTOS.md).

## Rutas del inventario sin método en el núcleo

`orchestration/inventario-rutas-gns3.txt` reúne **361 líneas** de rutas extraídas de los
decoradores `@Route` de `gns3server` 2.2.61. Sólo la API del **controlador** (`:3080`) es
operable desde este repo: `GET /v2/qemu/images` y `GET /v2/capabilities` devuelven 404 porque
viven en el compute.

Se considera **sin método** lo que no existe en `gns3core.py`, no lo que no tenga consumidor:
todo lo que está en `API_V2_MAP` tiene método y consumidor en CLI o MCP.

### Internas de compute (NIO y capturas por puerto)

No son funcionalidad de usuario: son el cableado y la captura dentro del proceso de compute. El
área `nio_ports` las expone con `port_nio()` y `port_capture()` contra el compute local. La
tabla de handlers sigue siendo el inventario de rutas disponibles:

| handler | rutas | NIO | capturas | pcap |
|---|---:|---:|---:|---:|
| `api/compute/atm_switch_handler.py` | 13 | 2 | 2 | 1 |
| `api/compute/cloud_handler.py` | 13 | 3 | 2 | 1 |
| `api/compute/docker_handler.py` | 19 | 3 | 2 | 1 |
| `api/compute/dynamips_vm_handler.py` | 23 | 3 | 2 | 1 |
| `api/compute/ethernet_hub_handler.py` | 13 | 2 | 2 | 1 |
| `api/compute/ethernet_switch_handler.py` | 13 | 2 | 2 | 1 |
| `api/compute/frame_relay_switch_handler.py` | 13 | 2 | 2 | 1 |
| `api/compute/iou_handler.py` | 20 | 3 | 2 | 1 |
| `api/compute/nat_handler.py` | 13 | 3 | 2 | 1 |
| `api/compute/qemu_handler.py` | 27 | 3 | 2 | 1 |
| `api/compute/traceng_handler.py` | 15 | 3 | 2 | 1 |
| `api/compute/virtualbox_handler.py` | 18 | 3 | 2 | 1 |
| `api/compute/vmware_handler.py` | 19 | 3 | 2 | 1 |
| `api/compute/vpcs_handler.py` | 17 | 3 | 2 | 1 |

Las demás rutas de esos handlers (crear/borrar/arrancar/parar el nodo, listar imágenes, reset y
WS de consola) también son internas de compute: el repo hace lo equivalente por las rutas
genéricas del controlador.

### Funcionalidad de usuario sin método

| handler | ruta(s) | por qué no está cubierta |
|---|---|---|
| `api/controller/node_handler.py` | `GET /v2/projects/{id}/nodes/{nid}/console/ws` | websocket: `console_ws_url()` compone la URL; el canal lo abre el cliente |
| `api/controller/notification_handler.py` | `GET /v2/notifications/ws` | `notifications_ws_url()` compone la URL; `watch` y `gns3_events` abren el canal fuera del núcleo |
| `api/controller/project_handler.py` | `GET /v2/projects/{id}/notifications/ws` | ídem, con `notifications_ws_url(pid)` |
| `api/controller/server_handler.py` | `POST /v2/version` | cambia la versión informada; sin método en el núcleo |
| `api/controller/compute_handler.py` | `GET /v2/computes/endpoint/{id}/{emulator}/{action}` | `compute_endpoint()` y `gns3_compute_endpoint` resuelven la URL; `compute_action()` no la usa |
| `api/controller/link_handler.py` | `GET /v2/projects/{id}/links/{lid}` (detalle) | `link_get()` y `gns3_link_get`; la CLI no tiene verbo `get` |
| `api/controller/drawing_handler.py` | `GET /v2/projects/{id}/drawings/{did}` (detalle) | `drawing_get()` y `gns3_drawing_get`; la CLI no tiene verbo `get` |
| `index_handler.py` | `/`, `/debug`, `/upload`, `/compute`, `/controller`, `/projects/{id}`, `/static/web-ui/{filename}` | rutas de la web UI, no API de operación |

Ver también [GUI-PORTADA.md](GUI-PORTADA.md), [NIO-Y-CAPTURAS.md](NIO-Y-CAPTURAS.md),
[EVENTOS.md](EVENTOS.md), [LIMITES-CONTROLLER-COMPUTE.md](LIMITES-CONTROLLER-COMPUTE.md),
[COMPATIBILIDAD.md](COMPATIBILIDAD.md) y [PARIDAD.md](PARIDAD.md).
