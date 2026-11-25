# Eventos en vivo: WebSocket y stream HTTP

Secciones: URLs · Formato de cada evento · Eventos que se pueden esperar · Cómo suscribirse desde este repo.

GNS3 2.2 expone dos vías de notificación. El repo tiene las dos: HTTP con `notify` y WebSocket
con `watch` / `gns3_events`; el núcleo sólo compone la URL del WebSocket.

## URLs

| Ámbito | URL del handler | Método del núcleo |
|---|---|---|
| Controller, global | `ws://<host>:<puerto>/v2/notifications/ws` | `Client.notifications_ws_url()` sin argumento |
| Controller, un proyecto | `ws://<host>:<puerto>/v2/projects/{id}/notifications/ws` | `Client.notifications_ws_url(pid)` |
| Compute (no expuesto por este repo) | `ws://<host>:<puerto>/v2/compute/notifications/ws` | — |

`notifications_ws_url()` toma `self.url` y cambia `http://` por `ws://` (o `https://` por
`wss://`); no abre el socket. Las dos rutas del controller están en
`handlers/api/controller/notification_handler.py` y `project_handler.py`. La del compute está
en `handlers/api/compute/notification_handler.py` y `Route._route` le antepone `/v2/compute`.

El handler global lee de `controller.notification.controller_queue()` con timeout de 5 s por
lectura. El de proyecto lee de `project_queue(project.id)`, también a 5 s, y al desconectar
cierra el proyecto si tiene `auto_close` y ya no quedan listeners. Suscribirse a la WS de un
proyecto puede, por tanto, cambiar el estado del proyecto al salir.

## Formato de cada evento

`NotificationQueue.get_json()` serializa cada mensaje como JSON con tres claves:

```json
{"action": "node.updated", "event": {...}, "project_id": "…"}
```

`action` es el nombre del evento y `event` su contenido. `project_id` y `compute_id` aparecen
cuando el emisor los añade; en el stream global suelen faltar.

## Eventos que se pueden esperar

Leídos de los `controller_emit`/`project_emit` y `emit` de los handlers de `gns3server` 2.2.61
instalado en esta máquina. No todos se disparan en toda operación.

| Stream | Eventos observados en el código |
|---|---|
| `/v2/notifications/ws` (controller) | `compute.created`, `compute.updated`, `compute.deleted`, `template.created`, `template.updated`, `template.deleted`, `project.created`, `log.warning` |
| `/v2/projects/{id}/notifications/ws` | `node.created`, `node.updated`, `node.deleted`, `link.created`, `link.updated`, `link.deleted`, `project.created`, `project.updated`, `project.opened`, `project.closed`, `project.deleted`, `ping`, `log.info`, `log.warning`, `log.error` |

`node.updated` se reenvía desde el compute: el controlador actualiza su copia del nodo y vuelve
a emitir el evento hacia el stream del proyecto
(`controller/notification.py::dispatch`). `ping` llega con `compute_id`. Los `log.*` llevan
`{"message": "…"}` dentro de `event`.

## Cómo suscribirse desde este repo

**Vía HTTP (sí existe).** `Client.notifications(pid=None)` hace `GET /v2/notifications` o
`GET /v2/projects/{id}/notifications`. Es un stream chunked, línea a línea, que no termina por
sí solo. La CLI `gns3lab notify [proyecto] [--count N] [--json]` lee un número acotado de
líneas (`_notify_snapshot`) para no colgarse. La tool `gns3_notifications(project_id,
project_name)` existe y devuelve la respuesta tal cual; al ser un stream permanente, conviene
usarla con timeout corto en el cliente.

**Vía WebSocket (existe).** El núcleo compone la URL con `notifications_ws_url()`; el canal lo
abren la CLI y el MCP, no el núcleo:

| Superficie | Comando o tool | Cómo |
|---|---|---|
| CLI | `gns3lab watch [--project P] [--seconds N]` | handshake WebSocket con la stdlib, lee frames hasta el timeout y sale |
| MCP | `gns3_events_url(project_id, project_name)` | devuelve la URL y una nota de suscripción |
| MCP | `gns3_events(action="url\|listen", seconds=5)` | `listen` conecta con `websockets`, lee hasta el timeout y devuelve `events` |

En ambos casos: abrir la URL de la tabla, leer mensajes hasta el timeout, parsear el JSON y
filtrar por `action`; si no conecta, imprimir la URL y el error literal, nunca quedarse colgado.
El servidor atiende ping/pong con `process_websocket()`.

```bash
gns3lab watch --project examen-kit --seconds 5
```

Confirma `WebSocket: ws://...` en `stderr` y una línea por evento; al final, el número de
eventos leídos. Si no conecta, sale con código 1 y deja la URL y el error en `stderr`.

Ver [NIO y capturas](NIO-Y-CAPTURAS.md) y
[Límites controller/compute](LIMITES-CONTROLLER-COMPUTE.md). El informe
[REA de ubridge](research/ubridge-console-enganche.md) descarta que la consola o estos eventos
salgan del binario ubridge.
