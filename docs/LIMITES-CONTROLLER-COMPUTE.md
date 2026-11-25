# Límites entre controller y compute

Un `gns3server` 2.2 sirve dos API en el mismo proceso. `Route._route`
(`gns3server/web/route.py`) decide el prefijo según el módulo del handler:

- `handlers/api/controller/*` → `/v2/…`
- `handlers/api/compute/*` → `/v2/compute/…`
- `handlers/index_handler.py` → sin prefijo (páginas HTML y compatibilidad)

El cliente de este repo apunta al **controller** (`Client.url`, normalmente
`http://127.0.0.1:3080`). Las rutas del compute se alcanzan por la pasarela
`/v2/computes/{id}/{emulator}/{action:.+}` (`handlers/api/controller/compute_handler.py`,
verbos `GET`/`POST`/`PUT`), que llama a `compute.forward()` y éste al compute. No todas las
rutas del compute tienen pasarela: las WS de consola y de notificaciones se componen como URL,
no se abren desde el núcleo.

## Qué manda cada uno

| Dueño | Rutas | Métodos de `gns3core` |
|---|---|---|
| Controller | `/v2/projects`, `/nodes`, `/links`, `/drawings`, `/snapshots`, `/templates`, `/symbols`, `/computes` (administración), `/gns3vm`, `/iou_license`, `/notifications`, `/version` | `projects`, `nodes`, `link_capture`, `templates`, `symbols`, `gns3vm*`, `notifications`, `version` |
| Compute (vía proxy) | `/computes/local/projects/{id}/{emu}/nodes/{nid}/adapters/{a}/ports/{p}/nio` y `/…/{start_capture\|stop_capture\|pcap}` | `port_nio`, `port_capture` |
| Compute (vía proxy) | `/computes/local/qemu/binaries`, `/capabilities`, `/img-binaries`, `/img`, `/computes/local/{virtualbox\|vmware}/vms`, `/vmware/nodes/interfaces/vmnet`, `/network/{interfaces\|ports}`, `/ports/udp` | `qemu_binaries`, `qemu_capabilities`, `qemu_img_binaries`, `qemu_img_config`, `virtualbox_vms`, `vmware_vms`, `vmware_vmnet`, `network_interfaces`, `network_ports`, `udp_port` |
| Compute (sólo URL) | `/v2/computes/{id}/projects/{pid}/{emu}/nodes/{nid}/console/ws`, `/v2/notifications/ws` de proyecto | `console_ws_url`, `notifications_ws_url` |

Las rutas genéricas `/v2/projects/{id}/nodes…` son del controller y luego se reenvían al compute
correspondiente; por eso funcionan con computes remotos. Las rutas `/computes/local/…` son
explícitamente locales: con un compute remoto (GNS3 VM) hay que cambiar `local` por el id del
compute. Los métodos `port_nio`/`port_capture` fijan `local`, igual que `qemu_images` y
`compute_write_file`.

## Por qué algunas rutas devuelven 409 sin VirtualBox/VMware

`VirtualBoxError` y `VMwareError` heredan de `NodeError`. `web/route.py` captura `NodeError` y
responde `409` con cuerpo `{"message": …, "status": 409, "exception": "…"}`. No es un error de
sintaxis ni un conflicto de estado del laboratorio: es que falta el hipervisor anfitrión o no se
puede arrancar. Mensajes literales del código:

- `Could not find VBoxManage, please reboot if VirtualBox has just been installed`
- `Could not find VMware vmrun, please make sure it is installed`
- `VMware is not installed (vmware or vmplayer executable could not be found in $PATH)`
- `Cannot start VM because hardware virtualization (VT-x/AMD-V) is already used by another software like VMware or KVM (on Linux)`

También es 409 un tipo de NIO no soportado por el emulador (`NIO of type … is not supported`).
En cambio, un `500` es una excepción no controlada del compute: fallo interno real, con traceback
en el `message` si se llama al compute directo. A través de la pasarela del controller, el 500 se
convierte en `Internal server error <url>` y el traceback queda en el log del compute. En ambos
casos `Client.req()` devuelve `(500, body)` y hay que mostrar el mensaje tal cual. Detalle en
[NIO y capturas](NIO-Y-CAPTURAS.md).

La traducción de estados en la pasarela está en `controller/compute.py::_run_http_query()`:
`409` del compute → `ComputeConflict` con el `message` original; `500` → `HTTPInternalServerError`
genérico; `404` → `HTTPNotFound`. La CLI y el MCP leen `message` con `_err`/`_err_msg` y no
inventan contenido.

## `/v1/version` sí, `/v2/controller` no

`handlers/index_handler.py` declara `@Route.get(r"/v1/version", description="Old 1.0 API")`,
que devuelve `{"version": __version__}` del mismo proceso. Es un puente de compatibilidad con
clientes antiguos; por eso no lleva `/v2`. El núcleo lo expone como `Client.v1_version()` y
`API_V2_MAP` lo incluye en el área `nio_ports` (`GET /{v1|v2}/version`).

No existe `/v2/controller`: el prefijo `/v2` se reserva para los handlers bajo
`handlers/api/controller/`, que exponen recursos concretos (`/v2/computes`, `/v2/projects`,
`/v2/templates`…), no un objeto «controller» direccionable como tal. Sí existe `/controller`,
pero es una página HTML de diagnosis (`response.template("controller.html", controller=…)`), no
una ruta de la API. El inventario
[orchestration/inventario-rutas-gns3.txt](../orchestration/inventario-rutas-gns3.txt) no contiene
ninguna ruta `/v2/controller`.

Consecuencia práctica: para saber qué controller hay delante, usar `GET /v2/version` (o
`gns3lab servers` / `gns3_status`); `/v1/version` sólo confirma la versión del servidor para
clientes v1. Para operar, las rutas son las de cada recurso, nunca `/v2/controller`.

Ver [EVENTOS.md](EVENTOS.md), [API-COVERAGE.md](API-COVERAGE.md) y
[COMPATIBILIDAD.md](COMPATIBILIDAD.md).
