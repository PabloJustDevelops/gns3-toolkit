# Paridad CLI ↔ MCP

Secciones: Servidor y proyectos · Computes, imágenes y catálogo · Plantillas · Nodos · Enlaces, dibujos y snapshots · Consola y pantalla · Capturas, NIO y eventos · Sólo en un lado · Cómo se comprueba.

Una fila por operación. La columna CLI cita el verbo real de `gns3lab`; la del MCP, la tool y
su acción. Ambas se comprueban con el código: `cli/gns3lab` (dict `handlers`) y
`gns3_mcp_server.py` (funciones decoradas con `@mcp.tool`).

- `—`: no existe en ese lado.
- Consulta [COMANDOS.md](COMANDOS.md) para flags y ejemplos; [API-COVERAGE.md](API-COVERAGE.md)
  para el endpoint que hay detrás.

## Servidor y proyectos

| Operación | CLI (`gns3lab`) | MCP (`gns3`) |
|---|---|---|
| Estado del servidor | `servers`, `status`, `doctor` | `gns3_status` |
| Version v1 | `version-v1` | `gns3_status` (`version_v1`) |
| Estadísticas de computes | `stats` | `gns3_statistics` |
| Listar proyectos | `status` | `gns3_projects` (list) |
| Crear proyecto | `new` | `gns3_projects` (create) |
| Abrir / cerrar | `up`, `down` | `gns3_projects` (open/close); el resto abre solo |
| Borrar proyecto | — | `gns3_projects` (delete) |
| Renombrar / actualizar | — | `gns3_projects` (update) |
| Duplicar proyecto | `project duplicate` | `gns3_project_io` (duplicate) |
| Cargar `.gns3` desde ruta | `project load` | `gns3_project_io` (load) |
| Estadísticas del proyecto | `project stats` | `gns3_project_stats` |
| Ficheros del proyecto | `project file get|put` | `gns3_project_files` (get/put) |
| Exportar / importar `.gns3p` | `export`, `import`, `port` | `gns3_project_io` (export/import) |
| Kit de examen | `examen setup|verify|reset|informe` | `gns3_informe` |
| Verificación por componente | `verify qemu|pf|vpcs` | `gns3_verify` |

## Computes, imágenes y catálogo

| Operación | CLI (`gns3lab`) | MCP (`gns3`) |
|---|---|---|
| Listar / detalle de compute | `compute [id]` | `gns3_compute` (list/info) |
| Alta, edición, borrado de compute | `compute add|update|rm` | `gns3_compute` (add/update/delete) |
| Puertos del compute | `compute ports` | `gns3_compute` (ports) |
| Auto idlepc del compute | `compute idlepc` | `gns3_compute` (idlepc) |
| Pasarela al compute | `compute action` | `gns3_compute` (call) |
| Listar imágenes | `images [--emulator]` | `gns3_images` |
| Subir imagen o disco | `upload` | `gns3_upload` |
| Símbolos | `symbols`, `symbol …` | `gns3_symbols` (list/dimensions/raw/default/upload) |
| Appliances | `appliances` | `gns3_appliances` |
| Rutas y binarios del servidor | — | `gns3_server_paths` |

## Plantillas

| Operación | CLI (`gns3lab`) | MCP (`gns3`) |
|---|---|---|
| Listar | `templates`, `template list` | `gns3_templates`, `gns3_template` (list) |
| Crear | `template create` | `gns3_template` (create) |
| Editar | `template update` | `gns3_template` (update) |
| Borrar | `template delete` | `gns3_template` (delete) |
| Duplicar | `template duplicate` | `gns3_template` (duplicate) |
| Base-config | `template base-config` | `gns3_template` (base-config) |
| Instanciar | `node add --template` | `gns3_template` (apply), `gns3_nodes` (add), `gns3_node_edit` (create) |

## Nodos

| Operación | CLI (`gns3lab`) | MCP (`gns3`) |
|---|---|---|
| Listar nodos y estado | `status` | `gns3_nodes` (list), `gns3_topology` |
| Añadir nodo | `node add` | `gns3_nodes` (add), `gns3_node_edit` (create) |
| Arrancar, parar, recargar, suspender | `node start|stop|reload|suspend`; `up`/`down` en bloque | `gns3_nodes`, `gns3_node_action` |
| Reanudar / pausar / despausar | `node resume|pause|unpause` | `gns3_node_action` |
| Acción masiva | `all start|stop|suspend|reload` | `gns3_nodes_bulk` |
| Borrar nodo | `node rm` | `gns3_nodes` (delete), `gns3_node_edit` (delete) |
| Duplicar nodo | `node dup` | `gns3_node_edit` (duplicate) |
| Editar propiedades | `node props` | `gns3_node_edit` (update) |
| VLANs del switch | `node switch` | `gns3_node_edit` (switch) |
| Clonar disco | `node disk` | `gns3_node_edit` (clone_disk) |
| Redimensionar disco | `node disk-resize` | `gns3_node_edit` (disk-resize) |
| Enlaces del nodo | `node links` | `gns3_node_edit` (links) |
| Idlepc del nodo | `node idlepc` | `gns3_node_edit` (idlepc) |
| Línea de comandos del nodo | `node line` | `gns3_command_line` |
| Leer / escribir fichero del nodo | — | `gns3_node_files` |

## Enlaces, dibujos y snapshots

| Operación | CLI (`gns3lab`) | MCP (`gns3`) |
|---|---|---|
| Listar enlaces | `link list` | `gns3_links` (list), `gns3_link_edit` (list) |
| Crear enlace | `link add` | `gns3_links` (add), `gns3_link_edit` (add) |
| Editar enlace | `link edit` | `gns3_links` (update) |
| Borrar enlace | `link rm` | `gns3_links`, `gns3_link_edit` (delete) |
| Filtros disponibles | `link filters` | `gns3_links` (filters) |
| Listar / crear dibujo | `draw`, `draw list` | `gns3_drawings` (list/text/rect) |
| Editar / borrar dibujo | `draw edit|rm` | `gns3_drawings` (update/delete) |
| Borrar todos los dibujos | — | `gns3_drawings` (clear) |
| Snapshots | `snap list|create|restore|delete` | `gns3_snapshots` (list/create/restore/delete) |

## Consola y pantalla

| Operación | CLI (`gns3lab`) | MCP (`gns3`) |
|---|---|---|
| Comandos por consola telnet | `exec` | `gns3_exec`, `gns3_console` |
| Consola interactiva por stdin | `console` | — |
| Reset de una consola / de todas | `console reset`, `console reset-all` | `gns3_console_control` (reset/reset-all) |
| URL WebSocket de la consola | `console url` | `gns3_console_control` (url) |
| Leer pantalla con OCR | `shot` | `gns3_monitor` (text/shot) |
| Escribir texto | `type` | `gns3_monitor` (type) |
| Pulsar teclas | `key` | `gns3_monitor` (key) |
| HMP crudo, estado o reset | `mon` | `gns3_monitor` (cmd/status/reset) |

## Capturas, NIO y eventos

| Operación | CLI (`gns3lab`) | MCP (`gns3`) |
|---|---|---|
| Captura de enlace | `capture <link> start|stop|pcap` | `gns3_capture` (start/stop/read) |
| Captura por puerto | `capture-port <nodo> start|stop|pcap` | `gns3_port_capture` |
| NIO de un puerto | `nio get|add|rm` | `gns3_nio` (get/set/delete) |
| Notificaciones HTTP | `notify` | `gns3_notifications` |
| Eventos WebSocket | `watch` | `gns3_events_url`, `gns3_events` (url/listen) |
| Lote de tools | — | `gns3_batch` |
| Informe Markdown | `examen informe` | `gns3_informe` |

## Sólo en un lado

**Sólo CLI:** `fix` (repara un `.gns3p` importado), `port` (porta proyecto y discos entre
servidores), `test` (conectividad VPCS), `servers`, `doctor` y `console` interactiva.

**Sólo MCP:** `gns3_topology`, `gns3_server_paths`, `gns3_node_files`, borrar y renombrar
proyectos, `gns3_drawings` (clear), `gns3_batch` y las resources/prompts.

## Cómo se comprueba

```bash
# 47 comandos: claves del dict handlers
./cli/gns3lab --help | sed -n '2p' | tr -d ' ' | tr ',' '\n' | wc -l

# 43 tools: decoradores @mcp.tool
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -c \
  "import asyncio,gns3_mcp_server as s; print(len(asyncio.run(s.mcp.list_tools())))"
```

Superficie por endpoint en [API-COVERAGE.md](API-COVERAGE.md); referencias de flags en
[COMANDOS.md](COMANDOS.md).
