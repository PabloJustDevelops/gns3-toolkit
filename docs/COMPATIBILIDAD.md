# Compatibilidad

Secciones: Qué significa «compatibilidad total» aquí · GNS3 3.x: no se declara soporte · Límites reales · Lo que este proyecto no es.

## Qué significa «compatibilidad total» aquí

Cubrir la API v2 que hace falta para **operar un laboratorio entero desde terminal**: proyectos,
plantillas, nodos, enlaces, capturas, dibujos, snapshots, computes, imágenes, símbolos,
appliances, consola telnet y monitor QEMU. «Total» no significa reimplementar la GUI ni la API
interna de cada emulador; significa que no hace falta abrir la interfaz gráfica para montar,
arrancar, inspeccionar, capturar y restaurar un escenario.

Criterio de «cubierto»: hay una función en `gns3core`, un verbo en `gns3lab` y una tool o acción
MCP. La matriz endpoint a endpoint está en [API-COVERAGE.md](API-COVERAGE.md); la paridad entre
los dos frentes, en [PARIDAD.md](PARIDAD.md).

| Área | Qué incluye | Estado |
|---|---|---|
| Proyectos | listar, crear, abrir, cerrar, borrar, exportar, importar, renombrar, duplicar, cargar, estadísticas y ficheros | cubierto |
| Plantillas | listar, crear, editar, borrar, duplicar, instanciar y `base-config` | cubierto |
| Nodos | listar, crear, editar, borrar, duplicar, arrancar/parar/recargar/suspender/reanudar, acciones en lote, ficheros, VLANs, disco, resize, enlaces, idlepc y línea de comandos | cubierto |
| Enlaces | listar, crear, editar, borrar, captura y `available_filters` | cubierto |
| Dibujos | listar, crear, editar y borrar | cubierto |
| Snapshots | listar, crear, restaurar y borrar | cubierto |
| Computes e imágenes | listar, detalle, alta/edición/borrado, puertos, idlepc, estadísticas, imágenes, símbolos y appliances | cubierto |
| Consola y monitor | telnet por prompt, sesión interactiva, reset, URL WS, HMP con OCR, teclas y texto | cubierto |
| Eventos | stream HTTP acotado y WebSocket con timeout | cubierto |
| pfSense | detectar interfaces, asignar, IP, DHCP, reglas, NAT, SSH y `config.xml` | cubierto |

Los huecos concretos, agrupados por handler y con la prueba de que la ruta existe, están en
[API-COVERAGE.md](API-COVERAGE.md#rutas-del-inventario-sin-método-en-el-núcleo).
Las operaciones de la GUI ya portadas al núcleo, con su comando y su tool, están en
[GUI-PORTADA.md](GUI-PORTADA.md).

## GNS3 3.x: no se declara soporte

Este cliente construye rutas `/v2` y autentica con Basic auth leída de
`~/.config/GNS3/2.2/gns3_server.conf`. GNS3 3.x usa `/v3`, login por token y otro esquema de
proyectos. **No hay servidor 3.x en este entorno para verificarlo** (2026-11-25), así que no se
declara compatibilidad: ni probada ni parcial.

**De dónde sale el inventario, y no de memoria.** El `gns3server` instalado aquí es la versión
**2.2.61** (`~/Applications/gns3/venv/lib/python3.14/site-packages/gns3server/version.py`) y su
código es Python legible en
`~/Applications/gns3/venv/lib/python3.14/site-packages/gns3server/handlers`. Las 361 rutas de
`orchestration/inventario-rutas-gns3.txt` se extrajeron de los decoradores `@Route.get`,
`@Route.post`, `@Route.put` y `@Route.delete` de ese árbol, no se recordaron ni se infirieron de
la documentación. Eso acota la verdad de la matriz a **2.2.61**:
para 3.x haría falta repetir la extracción sobre un servidor real, inexistente hoy.

Lo que habría que cambiar, sin poder afirmar hoy que baste:

- `base_url`: de `/v2` a `/v3` en `Client.req()` y en las rutas crudas de `gns3lab` y del MCP.
- Autenticación: sustituir Basic auth por login y cabecera `Authorization: Bearer <token>`, con
  su refresco y su almacenamiento fuera del repo.
- Esquema de proyectos: rehacer el inventario de endpoints y los campos de proyecto, nodo y
  plantilla contra la documentación de 3.x; no vale asumir que los cuerpos de 2.2 se aceptan.
- Notificaciones y consola: revisar si siguen siendo websocket y con la misma ruta.
- Y volver a pasar la matriz de [API-COVERAGE.md](API-COVERAGE.md) contra un servidor 3.x real.

Mientras eso no exista y no se pruebe, la respuesta es la misma: **sólo GNS3 2.2.x**.

## Límites reales

- **`upload` y `clone_disk` sólo sobre el compute local.** Los dos leen y escriben en
  `~/GNS3/images/QEMU` y suben a `/v2/computes/local/...`. `gns3lab port` también sube al
  compute `local` del destino. En un servidor remoto el disco tiene que estar ya allí o subirse
  por otra vía.
- **`console` no se fija por `PUT` en el nodo.** La API responde 200 y lo ignora. Se fija en la
  plantilla: `POST` de la plantilla, `PUT` aparte con `console` y `GET` de verificación. La CLI
  (`template create --console`) y el MCP (`gns3_template` con `console`) ya lo hacen así.
- **OCR a 720x400.** El framebuffer de la fuente VGA 9x16 se lee a escala x2 y `--psm 4`; a
  escala x1 confunde `w` con `u`. No espera leer texto pequeño ni ventanas gráficas.
- **El monitor HMP es local.** `shot`, `type`, `key` y `mon` localizan el proceso QEMU en
  `/proc` y hablan con su `-monitor tcp` en `127.0.0.1`; necesitan el nodo arrancado en este
  equipo y `/proc` legible.
- **Las capturas se guardan y se resumen, no se diseccionan.** Se descarga el `.pcap` y, si hay
  `tshark`, se muestran las primeras líneas; el análisis de paquetes es de `tshark`/Wireshark.

## Lo que este proyecto no es

- No es un cliente de GNS3 3.x.
- No sustituye al VNC para instaladores interactivos con ratón.
- No es un cliente completo de la API: la lista de lo que falta está en
  [API-COVERAGE.md](API-COVERAGE.md).
