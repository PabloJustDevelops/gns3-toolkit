# Cobertura de la API v2

`gns3core.API_V2_MAP` declara **11 áreas**: `server`, `computes`, `projects`, `templates`,
`nodes`, `links`, `drawings`, `snapshots`, `symbols`, `gui_admin` y `emulators` (las 8 originales
más las tres añadidas con la GUI operativa). Esto es lo que hay detrás de cada una en este árbol
(2026-11-25): método del núcleo, verbo de `gns3lab`, tool MCP y test.

**Cómo está verificado.** Servidor GNS3 2.2.61 en `http://127.0.0.1:3080`, sólo `GET` de
lectura: `200` = ruta viva; `405` o `403` = ruta viva con otro método; `409` = captura no
iniciada; timeout = descarga o stream en curso. El inventario se contrastó con
`gns3server/handlers/api/` de la instalación local.

**Leyenda**

- `—`: no existe en ese lado.
- `†`: el método existe en `Client` pero todavía no lo consume ni la CLI ni el MCP.
- `contrato`: nombre acordado en `orchestration/BRIEF-cli.md` o `BRIEF-mcp-paridad.md`; ese
  carril aún no está en este árbol.
- `pendiente`: sin test en `tests/`.
- `en curso`: nombre acordado en `BRIEF-guicli.md`/`BRIEF-guimcp.md` que aún no está en este
  árbol (`gns3lab --help` da 30 subcomandos y `mcp.list_tools()` da 26 tools, sin esas acciones).
  El método del núcleo sí existe y está verificado.

La superficie ampliada de `Client` (`computes`, `compute`, `statistics`, `symbols`,
`appliances`, `images`, `project_get/close/delete`, `template_get/update/delete`,
`node_action`, `node_command_line`, `link_update/link_delete/link_capture`,
`drawing_update/drawing_delete`, `snapshots/snapshot_create/restore/delete`,
`drawings/drawing_create`, `compute_write_file`) y la de la GUI operativa (`node_resize_disk`,
`console_reset`, `console_ws_url`, `node_links`, `node_idlepc`, `link_available_filters`,
`project_stats/duplicate/load`, `project_file_read/write`,
`compute_create/update/delete/ports/auto_idlepc/action`, `gns3vm*`, `notifications`,
`template_duplicate/base_configs/base_config`, `symbol_dimensions/raw/raw_upload/default_symbols`,
`iou_license*`, `server_shutdown/reload/debug`, `qemu_binaries/capabilities`, `docker_images`,
`network_interfaces/ports`, `udp_port`) están en el núcleo y **todavía no tienen consumidor**
en este árbol: las conectan los carriles `opencode/cli` y `opencode/mcp`, y las de la GUI
operativa los carriles `opencode/guicli` y `opencode/guimcp`. Por eso muchas filas llevan `†`.

## server

| endpoint | método de `gns3core` | CLI | MCP | test |
|---|---|---|---|---|
| `GET /v2/version` | `version()`, `alive()` | `servers`, `status`, `doctor` | `gns3_status` | `test_client.py::test_alive_contra_servidor_levantado` |

Sondeo: `GET /v2/version` → 200, `{"version": "2.2.61"}`.

Además, `GET /v2/statistics` está asignado al área `computes` en el mapa.

## computes

| endpoint | método de `gns3core` | CLI | MCP | test |
|---|---|---|---|---|
| `GET /v2/computes` | `computes()†` | `doctor` (los lista) | `gns3_status` (resumen) | — |
| `GET /v2/computes/{id}` | `compute(cid)†` | `compute [id]` (contrato) | `gns3_compute` (contrato) | pendiente |
| `GET /v2/statistics` | `statistics()†` | `stats` (contrato) | `gns3_statistics` (contrato) | pendiente |
| `GET /v2/computes/{id}/{emulator}/images` | `images()†`, `qemu_images()` | `images` (sólo qemu) | `gns3_images` (sólo qemu) | — |
| `POST /v2/computes/{id}/{emulator}/images/{filename}` | `compute_write_file()†` (CLI y MCP hacen `POST` crudo) | `upload` | `gns3_upload` | pendiente |

Sondeo: `GET /v2/computes`, `/v2/computes/local`, `/v2/statistics` y
`/v2/computes/local/qemu/images` → 200.

## projects

| endpoint | método de `gns3core` | CLI | MCP | test |
|---|---|---|---|---|
| `GET/POST /v2/projects` | `projects()`; `POST` en crudo | `status`, `fix`, `port` (GET); `new` (POST) | `gns3_projects` (list/create) | `test_client.py::test_projects_devuelve_la_lista`, `::test_projects_propaga_el_error_http` |
| `GET/PUT/DELETE /v2/projects/{id}` | `project_get()†`; `PUT`/`DELETE` en crudo | `status` (GET); `import` y `port` (PUT del nombre) | `gns3_projects` (info/delete); `gns3_project_io` (PUT al importar) | pendiente |
| `POST /v2/projects/{id}/open` | `ensure_open()` | `up`, `new`, `port` | `_ensure_open()` en todas las tools; `gns3_projects` (open) | pendiente |
| `POST /v2/projects/{id}/close` | `project_close()†` | `down` | `gns3_projects` (close) | pendiente |
| `GET /v2/projects/{id}/export` | — (`GET` crudo con `raw=True`) | `export`, `port` | `gns3_project_io` (export) | pendiente |
| `POST /v2/projects/{id}/import` | — (`POST` crudo) | `import`, `port` | `gns3_project_io` (import/duplicate) | pendiente |

Sondeo: `GET /v2/projects` y `GET /v2/projects/{id}` → 200; `GET .../open`, `.../close` e
`.../import` → 405.

## templates

| endpoint | método de `gns3core` | CLI | MCP | test |
|---|---|---|---|---|
| `GET /v2/templates` | `templates()` | `templates`, `template list`, `node add` | `gns3_templates`, `gns3_template` (list), `gns3_nodes` (add) | — |
| `GET/PUT/DELETE /v2/templates/{id}` | `template_get/update/delete()†` (CLI y MCP hacen `GET`/`PUT`/`DELETE` crudos) | `template create` (PUT de `console` + GET de verificación), `template delete` | `gns3_template` (create y delete) | pendiente |
| `POST /v2/templates` (fuera del mapa) | — (`POST` crudo) | `template create` | `gns3_template` (create) | pendiente |
| `POST /v2/projects/{id}/templates/{tid}` | — (`POST` crudo) | `node add` | `gns3_nodes` (add), `gns3_template` (apply), `gns3_node_edit` (create) | pendiente |
| `GET /v2/appliances` | `appliances()†` | `appliances` (contrato) | `gns3_appliances` (contrato) | pendiente |

Sondeo: `GET /v2/templates` y `/v2/appliances` → 200.

## nodes

| endpoint | método de `gns3core` | CLI | MCP | test |
|---|---|---|---|---|
| `GET/POST /v2/projects/{id}/nodes` | `nodes()`; `POST` en crudo | `status` (GET) | `gns3_nodes` (list), `gns3_node_edit` (create sin plantilla) | `test_client.py::test_nodes_pide_el_proyecto_correcto` |
| `GET/PUT/DELETE /nodes/{nid}` | `node_detail()`, `find_node()`; `PUT`/`DELETE` en crudo | `node props`, `node switch`, `node disk` (PUT); `node rm` | `gns3_node_edit` (update/switch/delete), `gns3_nodes` (delete), `gns3_command_line` (contrato: GET del detalle) | pendiente |
| `POST /nodes/{nid}/{start\|stop\|reload\|suspend\|duplicate}` | `node_action()`† (sin `duplicate`: `POST` crudo) | `up`/`down` (POST en crudo), `node dup` | `gns3_nodes` (start/stop/reload/suspend), `gns3_node_action` (contrato), `gns3_node_edit` (duplicate) | pendiente |
| `GET/POST /nodes/{nid}/files/{path}` | `node_file_read()`, `node_file_write()` | — | `gns3_node_files` | `test_files.py` (3 tests, sólo escritura) |
| `GET /v2/symbols` | `symbols()†` | `symbols` (contrato) | `gns3_symbols` (contrato) | pendiente |

Sondeo: `GET .../nodes` → 200; `GET .../nodes/{nid}` → 200; `POST .../duplicate`,
`.../start` y `.../stop` → 405; `GET /v2/symbols` → 200.

## links

| endpoint | método de `gns3core` | CLI | MCP | test |
|---|---|---|---|---|
| `GET/POST /v2/projects/{id}/links` | `links()`; `POST` en crudo | `link list`, `link add` | `gns3_links` (list/add), `gns3_link_edit` (list/add) | — |
| `GET/PUT/DELETE /links/{lid}` | `link_update()†`, `link_delete()†`; `GET` sin método propio | `link rm`; `link edit` (contrato) | `gns3_links` (delete), `gns3_link_edit` (delete), `gns3_links` (update, contrato) | pendiente |
| `POST /links/{lid}/{start_capture\|stop_capture}` | `link_capture()†` | `capture start`/`stop` (contrato) | `gns3_capture` (start/stop; `file_name`, contrato) | pendiente |
| `GET /links/{lid}/pcap` | `link_capture(action="pcap")†` | `capture pcap` (contrato) | `gns3_capture` (read) | pendiente |

Sondeo: `GET .../links` y `GET .../links/{lid}` → 200; `POST .../start_capture` → 405;
`GET .../pcap` → 409 (no hay captura activa).

## drawings

| endpoint | método de `gns3core` | CLI | MCP | test |
|---|---|---|---|---|
| `GET/POST /v2/projects/{id}/drawings` | `drawings()†`, `drawing_create()†` (CLI y MCP hacen `POST` crudo) | `draw` (sólo crear) | `gns3_drawings` (list, text, rect) | — |
| `GET/PUT/DELETE /drawings/{did}` | `drawing_update()†`, `drawing_delete()†`; `GET` sin método | `draw edit` y `draw rm` (contrato) | `gns3_drawings` (update contrato, delete/clear) | pendiente |

Sondeo: `GET .../drawings` → 200; `GET .../drawings/{id}` con id inventado → 404 JSON (la
ruta existe, el dibujo no).

## snapshots

| endpoint | método de `gns3core` | CLI | MCP | test |
|---|---|---|---|---|
| `GET/POST /v2/projects/{id}/snapshots` | `snapshots()†`, `snapshot_create()†` | `snap list`, `snap create` | `gns3_snapshots` (list/create) | pendiente |
| `POST /snapshots/{sid}/restore` | `snapshot_restore()†` | `snap restore` | `gns3_snapshots` (restore) | pendiente |
| `DELETE /snapshots/{sid}` | `snapshot_delete()†` | `snap delete` (contrato) | `gns3_snapshots` (delete) | pendiente |

Sondeo: `GET .../snapshots` → 200; `POST .../restore` → 405. Listar, crear y restaurar están en
CLI y MCP; borrar llega con el contrato de CLI y ya está en MCP.

## symbols

| endpoint | método de `gns3core` | CLI | MCP | test |
|---|---|---|---|---|
| `GET /v2/symbols` | `symbols()` † | `symbols` | `gns3_symbols` (list en curso) | pendiente |
| `GET /v2/symbols/{id}/dimensions` | `symbol_dimensions()` † | `symbol dimensions` (contrato, en curso) | `gns3_symbols(action="dimensions")` (contrato, en curso) | pendiente |
| `GET/POST /v2/symbols/{id}/raw` | `symbol_raw()`, `symbol_raw_upload()` † | `symbol raw`/`upload` (contrato, en curso) | `gns3_symbols(action="raw\|upload")` (contrato, en curso) | pendiente |
| `GET /v2/default_symbols` | `default_symbols()` † | `symbol default` (contrato, en curso) | `gns3_symbols(action="default")` (contrato, en curso) | pendiente |

Sondeo: `GET /v2/symbols` y `/v2/default_symbols` → 200; `GET /v2/symbols/{id}/dimensions` y
`.../raw` → 200.

## gui_admin

| endpoint | método de `gns3core` | CLI | MCP | test |
|---|---|---|---|---|
| `GET/PUT /v2/gns3vm` | `gns3vm()`, `gns3vm_update()` † | `gns3vm show`/`set` (contrato, en curso) | `gns3_gns3vm(action="show\|set")` (contrato, en curso) | pendiente |
| `GET /v2/gns3vm/engines`, `/engines/{e}/vms` | `gns3vm_engines()`, `gns3vm_vms()` † | `gns3vm engines`/`vms` (contrato, en curso) | `gns3_gns3vm(action="engines\|vms")` (contrato, en curso) | pendiente |
| `GET/PUT /v2/iou_license` | `iou_license()`, `iou_license_update()` † | `iou-license get`/`set` (contrato, en curso) | `gns3_iou_license` (contrato, en curso) | pendiente |
| `GET /v2/notifications`, `/projects/{id}/notifications` | `notifications()` † | `notify` (contrato, en curso) | `gns3_notifications` (contrato, en curso) | pendiente |
| `POST /v2/shutdown`, `/reload`, `/debug` | `server_shutdown()`, `server_reload()`, `server_debug()` † | `server shutdown\|reload\|debug --yes` (contrato, en curso) | `gns3_server(action=…, confirm=True)` (contrato, en curso) | pendiente |

Sondeo: `GET /v2/gns3vm`, `/iou_license`, `/notifications` → 200; los `POST` de shutdown, reload
y debug devuelven 405 con `GET` (ruta viva). No ejecutarlos contra el servidor real.

## emulators

| endpoint | método de `gns3core` | CLI | MCP | test |
|---|---|---|---|---|
| `GET /v2/computes/local/qemu/binaries` | `qemu_binaries()` † | `emulator qemu-binaries` (contrato, en curso) | `gns3_emulator(action="qemu-binaries")` (contrato, en curso) | pendiente |
| `GET /v2/computes/local/qemu/capabilities` | `qemu_capabilities()` † | `emulator qemu-capabilities` (contrato, en curso) | `gns3_emulator(action="qemu-capabilities")` (contrato, en curso) | pendiente |
| `GET /v2/computes/local/docker/images` | `docker_images()` † | `emulator docker-images` (contrato, en curso) | `gns3_emulator(action="docker-images")` (contrato, en curso) | pendiente |
| `GET /v2/computes/local/network/interfaces` | `network_interfaces()` † | `emulator interfaces` (contrato, en curso) | `gns3_emulator(action="interfaces")` (contrato, en curso) | pendiente |
| `GET /v2/computes/local/network/ports` | `network_ports()` † | `emulator ports` (contrato, en curso) | `gns3_emulator(action="ports")` (contrato, en curso) | pendiente |
| `POST /v2/computes/local/ports/udp` | `udp_port()` † | `emulator udp <puerto>` (contrato, en curso) | `gns3_emulator(action="udp", port=…)` (contrato, en curso) | pendiente |
| `GET /v2/projects/{id}/nodes/{nid}/dynamips/auto_idlepc` | `node_idlepc()` † | `node idlepc` (contrato, en curso) | `gns3_node_edit(action="idlepc")` (contrato, en curso) | pendiente |

Sondeo: `GET /v2/computes/local/qemu/binaries` → 200; las rutas de emulador del controlador
(`GET /v2/qemu/images`, `GET /v2/capabilities`) → 404: viven en el compute, no aquí.

## Rutas del inventario sin puente (agrupadas por handler)

El fichero `orchestration/inventario-rutas-gns3.txt` tiene **361 líneas** de rutas, extraídas de
`~/Applications/gns3/venv/lib/python3.14/site-packages/gns3server/handlers` (el brief las cifra
en 78; el recuento real del fichero es 361). Sólo la API del **controlador** (`:3080`) es
operable desde este repo: `GET /v2/qemu/images` y `GET /v2/capabilities` devuelven 404 porque
viven en el compute.

Se considera **sin puente** lo que no tiene método en `gns3core.py`, aunque tenga contrato en
los briefs (eso se marca `en curso` en las secciones anteriores). Se separa en dos grupos.

### Internas de compute (NIO y capturas por puerto)

No son funcionalidad de usuario: son el cableado y la captura dentro del proceso de compute.
El repo no las expone; para capturar un enlace usa la ruta del controlador
`POST /v2/projects/{id}/links/{lid}/start_capture` (`link_capture()`).

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

Las restantes rutas de esos handlers (crear/borrar/arrancar/parar el nodo de cada emulador,
listar imágenes, reset y WS de consola) también son internas de compute: el repo hace lo
equivalente por las rutas genéricas del controlador `/v2/projects/{id}/nodes…`. Otros handlers
de compute sin puente propio: `capabilities_handler.py` (`GET /capabilities`),
`network_handler.py` (`POST /ports/udp`, `GET /network/interfaces`, `GET /network/ports` — el
repo los llama por la pasarela `/v2/computes/local/...`), `notification_handler.py`
(`GET /notifications/ws`), `project_handler.py` (10 rutas de proyecto dentro del compute) y
`server_handler.py` (`GET /version`, `/statistics`, `/debug`).

### Funcionalidad de usuario sin puente

| handler | ruta(s) | por qué no está cubierta |
|---|---|---|
| `api/controller/node_handler.py` | `POST /v2/projects/{id}/nodes/{start\|stop\|suspend\|reload}` (en lote) | el repo itera nodo a nodo con `POST /nodes/{nid}/…` |
| `api/controller/node_handler.py` | `POST /v2/projects/{id}/nodes/console/reset` (global) | `console_reset()` resetea un nodo, no todos |
| `api/controller/node_handler.py` | `GET /v2/projects/{id}/nodes/{nid}/console/ws` | websocket: `console_ws_url()` compone la URL, no abre el canal |
| `api/controller/notification_handler.py` | `GET /v2/notifications/ws` | websocket; `notifications()` usa `GET /v2/notifications` |
| `api/controller/project_handler.py` | `GET /v2/projects/{id}/notifications/ws` | websocket sin método en el núcleo |
| `api/controller/server_handler.py` | `POST /v2/version` | cambia la versión informada; sin método en el núcleo |
| `api/controller/compute_handler.py` | `GET /v2/computes/endpoint/{id}/{emulator}/{action}` y `PUT /v2/computes/{id}/{emulator}/{action}` | pasarela y descarga de imágenes; `compute_action()` cubre sólo `GET`/`POST` |
| `api/controller/link_handler.py` | `GET /v2/projects/{id}/links/{lid}` (detalle) | `links()` da la lista; no hay `link_get()` |
| `api/controller/drawing_handler.py` | `GET /v2/projects/{id}/drawings/{did}` (detalle) | `drawings()` da la lista; no hay `drawing_get()` |
| `index_handler.py` | `/`, `/debug`, `/upload`, `/compute`, `/controller`, `/projects/{id}`, `/static/web-ui/{filename}`, `/v1/version` | rutas de la propia web UI, no API de operación de laboratorio |

Las rutas con método en el núcleo pero sin consumidor CLI/MCP están en las secciones
[symbols](#symbols), [gui_admin](#gui-admin) y [emulators](#emulators), no en esta lista.

Ver también [GUI-PORTADA.md](GUI-PORTADA.md), [COMPATIBILIDAD.md](COMPATIBILIDAD.md) y
[PARIDAD.md](PARIDAD.md).
