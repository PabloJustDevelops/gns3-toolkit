# NIO y capturas: enlace frente a puerto

Secciones: Captura de enlace · Captura por puerto · NIO de un puerto · Qué significa un 500 del compute · Estado verificado.

Hay dos capturas distintas. La de **enlace** es del controlador. La de **puerto** se reenvía al
compute. Confundirlas da un 404 o un 500. El informe
[REA de ubridge](research/ubridge-console-enganche.md) explica por qué el enganche de la
consola pasa por la API del compute y no por el binario ubridge.

| | Captura de enlace | Captura por puerto |
|---|---|---|
| Dueño de la ruta | controller (`:3080`) | compute local, vía proxy `/v2/computes/local/…` |
| Endpoint | `POST /v2/projects/{id}/links/{lid}/start_capture`, `stop_capture`; `GET …/pcap` | `POST /v2/computes/local/projects/{id}/{emu}/nodes/{nid}/adapters/{a}/ports/{p}/start_capture`, `stop_capture`; `GET …/pcap` |
| Método del núcleo | `link_capture(pid, lid, action, file_name)` (`start\|stop\|pcap`) | `port_capture(pid, nid, adapter, port, action, file_name, emulator)` (`start_capture\|stop_capture\|pcap`) |
| CLI | `gns3lab capture <link_id> start\|stop\|pcap [-p PROY]` | `gns3lab capture-port <nodo> start\|stop\|pcap --adapter N --port N [-p PROY]` |
| Tool MCP | `gns3_capture(action="start\|stop\|read", …)` | `gns3_port_capture(node, adapter, port, action="start\|stop\|pcap", …)` |

Las dos superficies existen en este árbol. `capture-port` pasa por el compute local y necesita el
nodo arrancado para capturar; `capture` es del controlador y funciona con computes remotos.

## Captura de enlace

El controlador guarda el pcap en el proyecto. `link_capture()` envía en `start`:

```json
{"data_link_type": "DLT_EN10MB", "capture_file_name": "capture-<lid>.pcap"}
```

`stop` no lleva body. `pcap` usa `GET` con `raw=True` y devuelve los bytes. Si la captura no
está iniciada, `GET …/pcap` responde `409`; es un estado esperado, no un fallo del servidor.
La tool `gns3_capture` añade `action="read"`, que resume el pcap con `tshark` si está
instalado.

## Captura por puerto

La ruta la sirve el compute y el controlador la reenvía
(`handlers/api/controller/compute_handler.py`: `GET/POST/PUT /computes/{id}/{emulator}/{action}`).
`port_capture()` infiere el emulador con `_emulator_for()` (lee `node_type` del nodo) salvo que
se pase `emulator="qemu"`, `"vpcs"`, `"docker"`… El body de `start_capture` es:

```json
{"capture_file_name": "port-<nid8>-<adapter>-<port>.pcap", "data_link_type": "DLT_EN10MB"}
```

El handler QEMU (`handlers/api/compute/qemu_handler.py`) lee `capture_file_name` y ubridge fija
`EN10MB` cuando no recibe protocolo. El esquema acepta `data_link_type`, pero no se promete
cambiar la DLT desde esta ruta. `pcap` también es `GET raw=True` con timeout de 180 s: mientras
la captura sigue activa, la descarga puede no terminar. Para el nombre por defecto, `stop`.

## NIO de un puerto

`port_nio(pid, nid, adapter, port, body=None, emulator=None, delete=False)` usa la misma ruta
compute con `/nio` al final:

| Llamada | Verbo | Efecto en el handler QEMU |
|---|---|---|
| `body=None` | `GET` | lee el NIO actual |
| `body={...}` | `PUT` | actualiza `filters` y `suspend` del NIO |
| `delete=True` | `DELETE` | borra el NIO |

El contrato de CLI es `gns3lab nio get|add|rm …` y el de MCP
`gns3_nio(action="get|set|delete", …)`. **Límite real**: crear un NIO UDP es `POST` en el
handler QEMU y sólo acepta `nio_udp`; cambiar `lport`/`rhost`/`rport` exige borrar y recrear.
El núcleo no expone ese `POST`, así que `nio add` (que hace `PUT`) no crea un NIO UDP nuevo:
sólo actualiza `filters` y `suspend` sobre el NIO existente.

Body mínimo del NIO, según `gns3server/schemas/nio.py:26-56`:

```json
{"type": "nio_udp", "lport": 10000, "rhost": "127.0.0.1", "rport": 20000}
```

Para `PUT`, el handler QEMU sólo aplica `filters` y `suspend` (`qemu_handler.py:337-349`).

## Qué significa un 500 del compute

`Client.req()` no lanza excepción por un código HTTP: devuelve `(500, body)`. `body` es un JSON
con `message` y `status`, o una cadena si no es JSON. Dos casos, según por dónde se llame:

- **Directo al compute**: `web/route.py` captura la excepción no controlada y responde 500 con
  el traceback de Python en `message`. Es un fallo interno real: bug del servidor, body que
  rompió un handler, permisos, etc.
- **A través de `/v2/computes/local/…`**: `controller/compute.py::_run_http_query()` convierte
  un 500 del compute en `HTTPInternalServerError` con texto `Internal server error <url>`. El
  traceback queda en el log del compute; la respuesta del controlador ya no lo trae.

Regla: mostrar el código y el `message` literales (`_err` en la CLI, `_err_msg` en el MCP), sin
disfrazar el 500 como éxito ni como un `409` de «captura no iniciada». Los `409` son otra cosa:
`NodeError` (por ejemplo `VirtualBoxError`/`VMwareError`) y las conflictos de captura se mapean
a 409; un 500 nunca es un estado normal de NIO/captura. Ver
[Límites controller/compute](LIMITES-CONTROLLER-COMPUTE.md).

## Estado verificado

Sin servidor GNS3: los métodos `port_nio`, `port_capture`, `link_capture`, `_emulator_for` y
`notifications_ws_url` están en `gns3core.py`; `API_V2_MAP` declara 12 áreas, `nio_ports` entre
ellas. La CLI tiene `nio`, `capture-port` y `capture`; el MCP tiene `gns3_nio`,
`gns3_port_capture` y `gns3_capture`. Los verbos y handlers citados se leyeron del `gns3server`
2.2.61 instalado en esta máquina, no de una sesión de captura real.

Matriz endpoint a endpoint en [API-COVERAGE.md](API-COVERAGE.md); operaciones de GUI en
[GUI-PORTADA.md](GUI-PORTADA.md); eventos en [EVENTOS.md](EVENTOS.md).
