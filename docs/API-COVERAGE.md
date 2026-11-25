# Cobertura de la API v2

`gns3core.API_V2_MAP` declara 8 áreas. Esto es lo que hay detrás de cada una en este árbol
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

La superficie ampliada de `Client` (`computes`, `compute`, `statistics`, `symbols`,
`appliances`, `images`, `project_get/close/delete`, `template_get/update/delete`,
`node_action`, `node_command_line`, `link_update/link_delete/link_capture`,
`drawing_update/drawing_delete`, `snapshots/snapshot_create/restore/delete`,
`drawings/drawing_create`, `compute_write_file`) está en el núcleo y **todavía no tiene
consumidor** en este árbol: la conectan los carriles `opencode/cli` y `opencode/mcp`. Por eso
muchas filas llevan `†`.

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

## Endpoints de 2.2.61 que este repo NO cubre

Sólo API del **controlador** (`:3080`). La API interna de cada emulador (`/v2/qemu/...`,
`/v2/vpcs/...`, `/v2/docker/...`) vive en el proceso de compute y el controlador no la expone:
`GET /v2/qemu/images` y `GET /v2/capabilities` devuelven 404. El repo opera el controlador.

**Servidor y aplicación**

- `POST /v2/shutdown`, `POST /v2/reload`, `POST /v2/debug` — GET → 405.
- `GET` y `PUT /v2/iou_license` — GET → 200.
- `GET /v2/notifications` — GET → 200; `GET /v2/notifications/ws` — websocket.
- `GET /v2/default_symbols` — GET → 200.
- `GET /v2/symbols/{symbol_id}/dimensions` — GET → 200; `GET` y `POST /v2/symbols/{symbol_id}/raw` — GET → 200.
- `GET` y `PUT /v2/gns3vm` — GET → 200; `GET /v2/gns3vm/engines` y
  `/v2/gns3vm/engines/{engine}/vms` — GET → 200.

**Computes**

- `POST /v2/computes`; `PUT` y `DELETE /v2/computes/{id}` — sin uso en el repo (`compute_handler.py`).
- `GET /v2/computes/{id}/ports` — GET → 200.
- `POST /v2/computes/{id}/auto_idlepc` — GET → 405.
- `GET /v2/computes/{id}/{emulator}/images/{filename}` (descarga de una imagen) — la petición
  de un qcow2 real se cortó a los 3 s con la transferencia en curso: ruta viva, sin uso.
- `GET`, `POST` y `PUT /v2/computes/{id}/{emulator}/{action}` (pasarela al compute:
  `binaries`, `capabilities`, `img`…) — `GET .../qemu/binaries` → 200.

**Proyectos**

- `GET /v2/projects/{id}/stats` — GET → 200.
- `POST /v2/projects/{id}/duplicate` — GET → 405.
- `GET` y `POST /v2/projects/{id}/files/{path}` — GET de un fichero inexistente → 404 JSON
  (handler vivo).
- `GET /v2/projects/{id}/notifications` — se queda esperando (stream); `/notifications/ws` es
  websocket.

**Plantillas**

- `POST /v2/templates/{id}/duplicate` — GET → 405.
- `GET /v2/templates/base-configs` — GET → 200.
- `GET` y `PUT /v2/templates/{id}/base-config/{filename}` — declaradas en el handler; sin uso.

**Nodos**

- `POST /v2/projects/{id}/nodes/{start\|stop\|suspend\|reload}` (en lote) — GET → 403 JSON.
  El repo itera nodo a nodo.
- `GET .../nodes/{nid}/links` — GET → 200.
- `POST .../nodes/{nid}/resize_disk` — GET → 405.
- `POST .../nodes/console/reset` y `POST .../nodes/{nid}/console/reset` — GET → 405.
- `GET .../nodes/{nid}/console/ws` — GET → 403 JSON (websocket).
- Dynamips: `GET .../nodes/{nid}/dynamips/idlepc_proposals` y
  `.../dynamips/auto_idlepc` — GET → 403 JSON; `POST .../dynamips/auto_idlepc`.

**Enlaces**

- `GET .../links/{lid}/available_filters` — GET → 200.
- `GET .../links/{lid}` (detalle) — GET → 200. `links()` devuelve la lista; no hay método de
  detalle.

**Dibujos**

- `GET .../drawings/{did}` (detalle) — no hay `drawing_get`; `drawings()` da la lista.

**Snapshots**

- Ninguno: listar, crear, restaurar y borrar están cubiertos.

Ver también [COMPATIBILIDAD.md](COMPATIBILIDAD.md) y [PARIDAD.md](PARIDAD.md).
