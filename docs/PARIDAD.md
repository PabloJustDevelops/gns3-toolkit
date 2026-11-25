# Paridad CLI ↔ MCP

Una fila por operación. Sirve para ver de un vistazo si algo está sólo en un lado.

- Los nombres con `*` son el contrato de los carriles `opencode/cli` y `opencode/mcp`
  (`orchestration/BRIEF-cli.md` y `BRIEF-mcp-paridad.md`); en este árbol todavía no existen.
- `—`: no existe en ese lado.
- Tests: `—` no hay prueba. El carril `opencode/tests` busca el 100% de `gns3core.py`; cuando
  entre, esta columna se actualiza.

## Servidor y proyectos

| Operación | CLI (`gns3lab`) | MCP (`gns3`) | Test |
|---|---|---|---|
| Estado del servidor | `servers`, `status`, `doctor` | `gns3_status` | `test_client.py::test_alive_contra_servidor_levantado` |
| Resolver proyecto por nombre, id o único abierto | todos los que llevan `-p` o posicional | `_resolve_project` en todas las tools | `test_client.py` (8 tests de `resolve_project`) |
| Listar proyectos | `status` | `gns3_projects` (list) | `test_client.py::test_projects_devuelve_la_lista` |
| Crear proyecto | `new` | `gns3_projects` (create) | — |
| Abrir proyecto | `up`, `new`, `port` | `gns3_projects` (open); el resto abre solo | — |
| Cerrar proyecto | `down` | `gns3_projects` (close) | — |
| Borrar proyecto | — | `gns3_projects` (delete) | — |
| Exportar `.gns3p` | `export`, `port` | `gns3_project_io` (export) | — |
| Importar `.gns3p` | `import`, `port` | `gns3_project_io` (import) | — |
| Duplicar proyecto | — | `gns3_project_io` (duplicate: export + import) | — |

## Computes, imágenes y catálogo

| Operación | CLI (`gns3lab`) | MCP (`gns3`) | Test |
|---|---|---|---|
| Listar computes | `doctor` | `gns3_status` (resumen) | — |
| Detalle de un compute | `compute [id]`* | `gns3_compute`* | — |
| Estadísticas del servidor | `stats`* | `gns3_statistics`* | — |
| Listar imágenes | `images` (qemu) | `gns3_images` (qemu) | — |
| Subir imagen o disco | `upload` | `gns3_upload` | — |
| Listar símbolos | `symbols`* | `gns3_symbols`* | — |
| Listar appliances | `appliances`* | `gns3_appliances`* | — |
| Rutas y binarios del servidor local | — | `gns3_server_paths` | — |

## Plantillas

| Operación | CLI (`gns3lab`) | MCP (`gns3`) | Test |
|---|---|---|---|
| Listar plantillas | `templates`, `template list` | `gns3_templates`, `gns3_template` (list) | — |
| Crear plantilla | `template create` | `gns3_template` (create) | — |
| Editar plantilla | `template update`* | — (`gns3_template` create ya fija `console`) | — |
| Borrar plantilla | `template delete` | `gns3_template` (delete) | — |
| Instanciar plantilla | `node add --template` | `gns3_template` (apply), `gns3_nodes` (add) | — |

## Nodos

| Operación | CLI (`gns3lab`) | MCP (`gns3`) | Test |
|---|---|---|---|
| Listar nodos y estado | `status` | `gns3_nodes` (list), `gns3_topology` | `test_client.py::test_nodes_pide_el_proyecto_correcto` |
| Añadir nodo | `node add` | `gns3_nodes` (add), `gns3_node_edit` (create) | — |
| Arrancar, parar, recargar, suspender | `up`, `down` (todo); `node start/stop/reload/suspend`* | `gns3_nodes` (start/stop/reload/suspend), `gns3_node_action`* | — |
| Borrar nodo | `node rm` | `gns3_nodes` (delete), `gns3_node_edit` (delete) | — |
| Duplicar nodo | `node dup` | `gns3_node_edit` (duplicate) | — |
| Editar propiedades | `node props` | `gns3_node_edit` (update) | — |
| VLANs del switch | `node switch` | `gns3_node_edit` (switch) | — |
| Clonar disco | `node disk` | `gns3_node_edit` (clone_disk) | — |
| Ver la línea de comandos de QEMU | — | `gns3_command_line`* | — |
| Leer fichero del nodo | — | `gns3_node_files` (sin `content`) | — |
| Escribir fichero del nodo | — | `gns3_node_files` (con `content`) | `test_files.py` (3 tests) |

## Enlaces y capturas

| Operación | CLI (`gns3lab`) | MCP (`gns3`) | Test |
|---|---|---|---|
| Listar enlaces | `link list` | `gns3_links` (list), `gns3_link_edit` (list) | — |
| Crear enlace | `link add` | `gns3_links` (add), `gns3_link_edit` (add) | — |
| Borrar enlace | `link rm` | `gns3_links` (delete), `gns3_link_edit` (delete) | — |
| Editar enlace (filtros) | `link edit`* | `gns3_links` (update)* | — |
| Iniciar o parar captura | `capture start/stop`* | `gns3_capture` (start/stop) | — |
| Descargar y resumir el pcap | `capture pcap`* | `gns3_capture` (read) | — |
| Nombrar el fichero de captura | — | `gns3_capture` (`file_name`)* | — |

## Dibujos y snapshots

| Operación | CLI (`gns3lab`) | MCP (`gns3`) | Test |
|---|---|---|---|
| Listar dibujos | — | `gns3_drawings` (list) | — |
| Crear nota o rectángulo | `draw` | `gns3_drawings` (text/rect) | — |
| Editar dibujo | `draw edit`* | `gns3_drawings` (update)* | — |
| Borrar un dibujo | `draw rm`* | `gns3_drawings` (delete) | — |
| Borrar todos los dibujos | — | `gns3_drawings` (clear) | — |
| Listar snapshots | `snap list` | `gns3_snapshots` (list) | — |
| Crear snapshot | `snap create` | `gns3_snapshots` (create) | — |
| Restaurar snapshot | `snap restore` | `gns3_snapshots` (restore) | — |
| Borrar snapshot | `snap delete`* | `gns3_snapshots` (delete) | — |

## Consola y pantalla

| Operación | CLI (`gns3lab`) | MCP (`gns3`) | Test |
|---|---|---|---|
| Ejecutar comandos por consola telnet | `exec` | `gns3_exec`, `gns3_console` | `test_console.py` (5 tests) |
| Consola interactiva por stdin | `console`* | — | — |
| Leer la pantalla con OCR | `shot` | `gns3_monitor` (text/shot) | `test_qemu.py` (HMP); OCR sin test |
| Escribir texto con `sendkey` | `type` | `gns3_monitor` (type) | `test_qemu.py` |
| Pulsar teclas | `key` | `gns3_monitor` (key) | `test_qemu.py`, `test_keymap.py` |
| Comando HMP crudo, estado o reset | `mon` | `gns3_monitor` (cmd/status/reset) | `test_qemu.py` |

## Sólo en un lado

**Sólo CLI:** `fix` (repara un `.gns3p` importado), `port` (porta proyecto y discos entre
servidores), `test` (conectividad VPCS), `servers` (lista de servidores de la config),
`doctor --json` y `console`* (consola interactiva por stdin; el MCP no la tiene).

**Sólo MCP:** `gns3_topology`, `gns3_server_paths`, borrar proyecto, duplicar proyecto (como
export + import), leer y escribir ficheros de nodo, `gns3_drawings` (clear) y el nombre de
fichero de captura.

**En ninguno de los dos:** estadísticas de proyecto (`GET /v2/projects/{id}/stats`), duplicado
directo por endpoint (proyecto y plantilla), acciones de nodo en lote, notificaciones, gestión
de computes (alta, edición, borrado, puertos, idlepc), descarga de imágenes por HTTP,
`base-config` de plantillas, `available_filters` de enlaces, detalle de un enlace o de un
dibujo, `console/reset` y `console/ws`. Las rutas están en
[API-COVERAGE.md](API-COVERAGE.md#endpoints-de-2261-que-este-repo-no-cubre).
