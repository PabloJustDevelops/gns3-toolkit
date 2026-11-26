# Componentes candidatos de GNS3 2.2

Inventario vivo de lo que GNS3 2.2 ofrece y este toolkit todavía no porta, con el criterio
de qué sirve para el examen del 1 de diciembre y qué sirve a cualquier usuario que opere un
laboratorio desde la terminal.

Base: `8877d8d`. Servidor instalado: GNS3 **2.2.61** en
`~/Applications/gns3/venv/lib/python3.14/site-packages/gns3server`. Las rutas de handler que
aparecen en la tabla son relativas a ese directorio.

## Cómo se ha leído

- `orchestration/inventario-rutas-gns3.txt`: **361 líneas**, una por ruta activa con
  `@Route` en `handlers/api/**` y `handlers/index_handler.py`; el `@Route` comentado de
  `symbol_handler.py` no cuenta. El inventario se regenera con el comando del final y el
  `diff` sale vacío contra la instalación actual.
- `gns3core.API_V2_MAP`: **12 áreas** (`server`, `computes`, `projects`, `templates`, `nodes`,
  `links`, `drawings`, `snapshots`, `symbols`, `gui_admin`, `emulators`, `nio_ports`).
- [`docs/API-COVERAGE.md`](../docs/API-COVERAGE.md) y
  [`docs/GUI-PORTADA.md`](../docs/GUI-PORTADA.md): qué método, verbo y tool consumen cada
  endpoint, y qué rutas quedan fuera del núcleo.
- [`docs/LIMITES-CONTROLLER-COMPUTE.md`](../docs/LIMITES-CONTROLLER-COMPUTE.md) y
  [`docs/NIO-Y-CAPTURAS.md`](../docs/NIO-Y-CAPTURAS.md): prefijos, proxy y límites reales.
- Sondas **GET** contra `http://127.0.0.1:3080` con las credenciales locales. No se abrió
  ningún proyecto, no se arrancó ningún nodo y no se escribió nada.

Leyenda de estado:

- `ya cubierto`: hay método en `gns3core` y consumidor en CLI o MCP; `(parcial)` cuando
  falta una variante o el método sólo funciona contra el compute `local`.
- `candidato`: la ruta existe en el servidor instalado y no hay método dedicado.
- `descartado con motivo`: no aporta operación de usuario, duplica otra ruta o falsea el
  diagnóstico.

Esfuerzo: **S** un método y un verbo/tool con tests; **M** toca núcleo, CLI y MCP, o añade
transporte binario; **L** cambia una suposición transversal (compute remoto) y arrastra docs.

## Tabla ordenada por valor

| # | Componente | Qué aporta | Cobertura actual (método / CLI / MCP) | Esfuerzo | Estado | Evidencia |
|---:|---|---|---|---|---|---|
| 1 | Ciclo de proyecto | Crear, abrir, cerrar, exportar/importar, duplicar, cargar y medir el laboratorio; llevar el kit al aula | `projects`, `ensure_open`, `project_get/close/delete/duplicate/load/stats` / `status`, `new`, `up`, `down`, `export`, `import`, `project ...` / `gns3_projects`, `gns3_project_io`, `gns3_project_stats` | — | ya cubierto | `gns3core.py::Client.projects` y `project_*`; `api/controller/project_handler.py` |
| 2 | Nodos | Ciclo de vida, duplicado, resize, consola, ficheros, enlaces e idlepc | `nodes`, `node_detail`, `node_action`, `nodes_action`, `node_resize_disk`, `console_reset/ws`, `node_file_*`, `node_links`, `node_idlepc` / `node ...`, `all ...`, `console ...` / `gns3_nodes`, `gns3_node_action`, `gns3_console_control`, `gns3_node_files`, `gns3_node_edit` | — | ya cubierto | `gns3core.py::Client.nodes` y `node_*`; `api/controller/node_handler.py` |
| 3 | Enlaces y captura de enlace | Unir nodos, aplicar filtros y bajar el pcap del enlace; base de VLANs y NAT | `links`, `link_update`, `link_delete`, `link_available_filters`, `link_capture` / `link ...`, `capture ...` / `gns3_links`, `gns3_link_edit`, `gns3_capture` | — | ya cubierto | `gns3core.py::Client.links` y `link_*`; `api/controller/link_handler.py` |
| 4 | Ficheros de proyecto | Leer y escribir `config.xml`, `startup-config` y capturas por ruta | `project_file_read`, `project_file_write` / `project file get\|put` / `gns3_project_files` | — | ya cubierto (sólo por ruta) | `gns3core.py::Client.project_file_*`; `api/controller/project_handler.py` |
| 5 | Plantillas, base-configs y appliances | Crear nodos desde plantilla, duplicar, listar el catálogo de appliances y sus base-configs | `templates`, `template_get/update/delete/duplicate`, `template_base_configs`, `template_base_config`, `appliances` / `templates`, `template ...`, `appliances`, `node add` / `gns3_templates`, `gns3_template`, `gns3_appliances` | — | ya cubierto | `gns3core.py::Client.templates` y `template_*`; `api/controller/template_handler.py`, `appliance_handler.py` |
| 6 | Símbolos | Iconos del lienzo, dimensiones, SVG y subida de un símbolo | `symbols`, `symbol_dimensions`, `symbol_raw`, `symbol_raw_upload`, `default_symbols` / `symbols`, `symbol ...` / `gns3_symbols` | — | ya cubierto | `gns3core.py::Client.symbols` y `symbol_*`; `api/controller/symbol_handler.py` |
| 7 | Snapshots | Punto de retorno antes de tocar pfSense, VLANs o NAT | `snapshots`, `snapshot_create/restore/delete` / `snap ...` / `gns3_snapshots` | — | ya cubierto | `gns3core.py::Client.snapshots` y `snapshot_*`; `api/controller/snapshot_handler.py` |
| 8 | Computes y emuladores locales | Estado, puertos, idlepc, binarios QEMU, imágenes Docker, interfaces/puertos y VMs invitadas | `computes`, `compute_*`, `statistics`, `qemu_binaries/capabilities`, `docker_images`, `network_interfaces/ports`, `udp_port`, `virtualbox_vms`, `vmware_*` / `compute ...`, `stats`, `emulator ...`, `vm ...`, `disk ...` / `gns3_compute`, `gns3_statistics`, `gns3_emulator` | — | ya cubierto (sólo compute `local`) | `gns3core.py::Client.computes` y `*_images`/`*_vms`; `docs/LIMITES-CONTROLLER-COMPUTE.md` |
| 9 | Imágenes de emulador | Listar y subir discos al compute local | `images`, `qemu_images`, `compute_write_file` / `images`, `upload` / `gns3_images`, `gns3_upload` | — | ya cubierto (sólo `local`) | `gns3core.py:181`, `gns3core.py:262`, `gns3core.py:409`; `api/controller/compute_handler.py` |
| 10 | NIO y captura por puerto | Enganche de ubridge y pcap por adaptador/puerto | `port_nio`, `port_capture` / `nio ...`, `capture-port ...` / `gns3_nio`, `gns3_port_capture` | — | ya cubierto (sólo `local`; sin `POST` de creación) | `gns3core.py:305-334`; `docs/NIO-Y-CAPTURAS.md` |
| 11 | Consola y eventos WS | Abrir la terminal y escuchar cambios sin VNC | `console_ws_url`, `notifications_ws_url` / `console url`, `watch` / `gns3_console_control`, `gns3_events*` | — | ya cubierto (URL; el canal lo abre el cliente) | `api/controller/node_handler.py`, `notification_handler.py`; `docs/EVENTOS.md` |
| 12 | Administración del servidor | Licencia IOU, GNS3 VM, notificaciones, estadísticas y shutdown/reload/debug | `iou_license*`, `gns3vm*`, `notifications`, `server_shutdown/reload/debug` / `iou-license ...`, `gns3vm ...`, `notify`, `server ...` / `gns3_iou_license`, `gns3_gns3vm`, `gns3_notifications`, `gns3_server` | — | ya cubierto | `api/controller/server_handler.py`, `gns3_vm_handler.py`; `gns3core.py::Client.iou_license` y `gns3vm*` |
| 13 | **Listado de ficheros de proyecto** | Saber qué hay antes de leer: `config.xml`, `startup-config`, capturas y artefactos del proyecto, sin adivinar rutas | — / `project file get\|put` (no hay `ls`) / `gns3_project_files` get/put (no hay list) | S | candidato | `api/compute/project_handler.py:216-233`; proxy `GET /v2/computes/{cid}/projects/{id}/files`; sonda 404 con proyecto cerrado, no verificada con proyecto abierto |
| 14 | **Detalle de enlace** | Estado exacto de un enlace (extremos, filtros, `capturing`, `capture_file_name`) sin traer toda la lista | — / `link list` (no hay `link get`) / `gns3_links list` (no hay get) | S | candidato | `api/controller/link_handler.py:102`; sonda 403 `The project is not opened` (ruta viva) |
| 15 | **Detalle de dibujo** | SVG, posición y rotación de una nota sin listar todo el proyecto | — / `draw list` (no hay `draw get`) / `gns3_drawings list` (no hay get) | S | candidato | `api/controller/drawing_handler.py:65`; sonda 403 `The project is not opened` (ruta viva) |
| 16 | **Descarga binaria desde compute** | Bajar pcap o imágenes de un compute remoto; el proxy del controller no sirve para binario | `compute_action` sólo JSON / `compute action` sólo JSON / `gns3_compute call` sólo JSON | M | candidato | `api/controller/compute_handler.py:100`; `api/compute/qemu_handler.py:543`; endpoint 200 y GET directo 200 (3.653.632 bytes); el proxy devolvió 500 al serializar |
| 17 | **Compute remoto** | Usar GNS3 VM o el servidor del aula en `images`, `upload`, `nio`, `capture-port`, `qemu-binaries` y el resto de rutas `/computes/local/...` | `compute_write_file(cid)` acepta id; `images`, `qemu_images`, `port_nio`, `port_capture`, `qemu_binaries` fijan `local` / verbos sin `--compute` / tools sin `compute_id` | M/L | candidato | `gns3core.py:181`, `262`, `305`, `320`, `557`; `docs/LIMITES-CONTROLLER-COMPUTE.md` |
| 18 | Idlepc de Dynamips | Propuestas además del `auto_idlepc` | `node_idlepc(proposals=True)` / `node idlepc` (sólo auto) / `gns3_node_edit idlepc` (sólo auto) | S | ya cubierto (parcial: propuestas sin verbo; no declarado en `API_V2_MAP`) | `api/controller/node_handler.py`; `gns3core.py::Client.node_idlepc` |
| 19 | `POST /v2/version` | Cambia la versión que el servidor informa | — | — | descartado: no opera el laboratorio y falsea el diagnóstico | `api/controller/server_handler.py`; `docs/API-COVERAGE.md` |
| 20 | Web UI | `/`, `/debug`, `/upload`, `/compute`, `/controller`, `/projects/{id}`, `/static/web-ui/{filename}` | — | — | descartado: HTML y estáticos, no API de operación | `handlers/index_handler.py`; `docs/API-COVERAGE.md` |
| 21 | NIO internos de compute | Rutas de NIO, `start_capture`, `stop_capture` y `pcap` por emulador | `port_nio` y `port_capture` cubren el caso de usuario en el compute local | — | descartado: cableado interno; el usuario usa `nio`/`capture-port` | `api/compute/*_handler.py`; `docs/NIO-Y-CAPTURAS.md` |
| 22 | Duplicados del compute | CRUD de proyectos, `/version`, `/statistics`, `/debug` y `/capabilities` en el proceso de compute | Los equivalentes del controller ya están cubiertos | — | descartado: duplican rutas; `computes()` ya trae las capacidades del compute y `/v2/capabilities` en el controller da 404 | `api/compute/project_handler.py`, `server_handler.py`, `capabilities_handler.py`; sonda `GET /v2/capabilities` → 404 |

## Límites de la verificación

No todo se pudo ejercitar contra el servidor instalado. Estos son los huecos, sin convertirlos
en cobertura:

- **Detalle de enlace y de dibujo**: la ruta está montada, pero la sonda devolvió
  `403 {"message": "The project is not opened", "status": 403}`. No se abrió ningún proyecto
  porque abrir es una escritura; el objeto de detalle no se ha leído en vivo.
- **Listado de ficheros de proyecto**: la sonda contra un proyecto cerrado devolvió `404` y no
  distingue entre «ruta inexistente» y «proyecto no cargado». La ruta está declarada en
  `api/compute/project_handler.py:217`, pero no se ha probado con un proyecto abierto.
- **Compute remoto**: el servidor solo tiene el compute `local`. La afirmación sobre `local`
  fijo sale del código (`gns3core.py`) y de `docs/LIMITES-CONTROLLER-COMPUTE.md`, no de una
  prueba contra una GNS3 VM.
- **Descarga binaria**: sí se comprobó de extremo a extremo con `OVMF_CODE.fd`: el endpoint
  devolvió `200` con la URL del compute y el GET directo devolvió `200` con **3.653.632**
  bytes. El mismo fichero por el proxy devolvió `500`; el detalle del binario no se replica
  aquí.

## Top 5 de candidatos

1. **Listado de ficheros de proyecto** (`GET /v2/compute/projects/{id}/files` directo, o el
   proxy `GET /v2/computes/{cid}/projects/{id}/files`). Es el hueco
   que más aprieta para `verify` y para el spec declarativo: permite comprobar que existe
   `config.xml`, `startup-config` o el pcap esperado antes de leerlo. Hoy `project file get`
   exige la ruta exacta y el spec no puede declarar artefactos sin adivinarla. Coste S.
2. **Detalle de enlace** (`GET /v2/projects/{id}/links/{lid}`). Da el objeto completo de un
   enlace, incluido `capturing` y `capture_file_name`, sin recorrer la lista entera. Es el
   complemento natural de `gns3lab verify link`. Coste S.
3. **Compute remoto**. `images`, `qemu_images`, `port_nio`, `port_capture` y `qemu_binaries`
   tienen `local` escrito en el código. Para el servidor del aula o una GNS3 VM hay que
   parametrizar el `compute_id` en núcleo, CLI y MCP. Es el candidato de más valor para otros
   usuarios y el de más coste (M/L); no bloquea el examen local.
4. **Descarga binaria desde compute**. El endpoint
   `GET /v2/computes/endpoint/{cid}/{emulator}/{action}` devuelve la URL directa del compute;
   el proxy `GET /v2/computes/{cid}/{emulator}/{action}` responde **500** cuando el cuerpo es
   binario. Sin esto no se puede bajar un pcap o una imagen de un compute remoto con el
   cliente actual. Coste M.
5. **Detalle de dibujo** (`GET /v2/projects/{id}/drawings/{did}`). Aporta poco al examen,
   pero cuesta S y cierra el mismo patrón que el detalle de enlace: listar y luego pedir uno.
   Si el carril de enlaces ya toca `gns3core`, hacerlo en la misma tanda evita otra ronda.

## Por qué se descarta el resto

- **Web UI** (`/`, `/debug`, `/upload`, `/compute`, `/controller`, `/projects/{id}`,
  `/static/web-ui/{filename}`). Son páginas HTML y estáticos de diagnosis. No operan el
  laboratorio y no aportan nada que no hagan las rutas `/v2` ya portadas.
- **NIO internos de compute**. Cada emulador repite `nio`, `start_capture`, `stop_capture` y
  `pcap`. El usuario no necesita esas rutas: `port_nio` y `port_capture` ya las usan a través
  del proxy para el compute local. El `POST` que crearía un NIO UDP nuevo sigue sin método,
  pero es una limitación del flujo de usuario, no una ruta que portar aquí.
- **`POST /v2/version`**. Cambia la versión que el servidor declara. No monta nada, no
  verifica nada y estropea `servers`, `status` y `doctor`, que leen `GET /v2/version`.
- **Duplicados del compute**. `project_handler`, `server_handler` y `capabilities_handler`
  del compute repiten CRUD, versión, estadísticas, debug y capacidades que el controller ya
  expone. `GET /v2/capabilities` en el controller devuelve 404; las capacidades útiles ya
  vienen dentro de `GET /v2/computes`.
- **Detalle de enlace y de dibujo no se descartan**: son los candidatos 2 y 5. Tampoco se
  descarta el resto de rutas de nodo, enlace, snapshot, plantilla, símbolo, proyecto y
  servidor: están cubiertas y no necesitan carril.

## Tres recomendaciones para los próximos dos carriles

1. **Carril `verify-enlace`**: implementar `link_get` y un `verify link` que compruebe, en
   solo lectura, que el enlace existe, tiene dos extremos y que `capturing` coincide con lo
   esperado. Encaja con el contrato `gns3lab verify <componente>` que prepara el carril de
   verificación; en la base `8877d8d` el único `verify` integrado es `gns3lab examen verify`.
   `drawing_get` es el compañero S del mismo patrón y puede entrar en la misma tanda.
2. **Carril `verify-artefactos` + spec**: añadir listado de ficheros de proyecto y una clave
   `expect.files` al YAML declarativo (`LAB-SPEC.md` del carril `gk10-spec`). `labspec verify`
   comprobaría que cada artefacto declarado existe y no está vacío; `gns3lab verify files`
   daría el mismo contrato por CLI. Es el hueco que hoy obliga a conocer rutas de antemano.
3. **Carril `compute-remoto`** (después del examen): parametrizar `compute_id` en las rutas
   que hoy fijan `local` y añadir la descarga por endpoint + GET directo. Con eso se pueden
   bajar imágenes y pcaps del servidor del aula y verificar un compute remoto. Es M/L y no
   bloquea el examen del 1 de diciembre, que se hace contra el compute local.

## Cómo se actualiza

Ejecutar desde la raíz del repo. El primer bloque regenera el inventario con el mismo formato
del fichero versionado; el `diff` debe salir vacío y no se sobrescribe nada del repo.

```bash
cd ~/Applications/gns3/venv/lib/python3.14/site-packages/gns3server
python3 - <<'PY' > /tmp/inventario-rutas-gns3.txt
import pathlib, re
pat = re.compile(r'@Route\.(get|post|put|delete)\(\s*(?:r?"([^"]+)"|uri=r?"([^"]+)")', re.S)
for p in sorted(pathlib.Path("handlers").rglob("*.py")):
    for m in pat.finditer(p.read_text(encoding="utf-8")):
        method = m.group(1).upper()
        uri = m.group(2) or m.group(3)
        print(f"{method:6} {uri:<58} {str(p).removeprefix('handlers/')}")
PY
wc -l /tmp/inventario-rutas-gns3.txt
diff -u ~/Proyectos/gns3-toolkit.gk10-discovery/orchestration/inventario-rutas-gns3.txt \
        /tmp/inventario-rutas-gns3.txt
```

Comprobar que la instalación sigue siendo 2.2.x antes de fiarse del inventario:

```bash
cd ~/Proyectos/gns3-toolkit.gk10-discovery
./cli/gns3lab servers
```

Recalcular las áreas de `API_V2_MAP` y contrastarlas con la documentación:

```bash
cd ~/Proyectos/gns3-toolkit.gk10-discovery
python3 - <<'PY'
import ast, re
s = open('gns3core.py').read()
d = ast.literal_eval(re.search(r'API_V2_MAP[^=]*= (\{.*?\n\})', s, re.S).group(1))
print(len(d), sorted(d))
for area, rutas in d.items():
    print(f"{area}: {len(rutas)}")
PY
env -u PYTHONPATH -u VIRTUAL_ENV python3 scripts/verify.py
python3 scripts/check-links.py
```

Al añadir una ruta nueva: actualizar `API_V2_MAP`, la tabla de
[`docs/API-COVERAGE.md`](../docs/API-COVERAGE.md), la fila correspondiente de
[`docs/GUI-PORTADA.md`](../docs/GUI-PORTADA.md) si tiene equivalente en la GUI, y esta tabla.
Las cifras de esta página no se copian de memoria: salen de los comandos de arriba.
