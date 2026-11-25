# Compatibilidad

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
| Proyectos | listar, crear, abrir, cerrar, borrar, exportar, importar, renombrar | cubierto; faltan `stats`, `duplicate` por endpoint (el MCP lo hace como export + import) y `files/{path}` |
| Plantillas | listar, crear, editar, borrar, instanciar | cubierto; faltan `duplicate` y `base-config` |
| Nodos | listar, crear, editar, borrar, duplicar, arrancar/parar/recargar/suspender, ficheros, VLANs, disco | cubierto; faltan acciones en lote, `resize_disk` y `console/reset` |
| Enlaces | listar, crear, editar, borrar, captura | cubierto; falta `available_filters` |
| Dibujos | listar, crear, editar, borrar | cubierto; editar y borrar llegan con el contrato de CLI/MCP |
| Snapshots | listar, crear, restaurar, borrar | cubierto |
| Computes e imágenes | listar, detalle, estadísticas, imágenes, símbolos, appliances | cubierto en el núcleo; detalle, estadísticas, símbolos y appliances llegan con los carriles CLI/MCP |
| Consola y monitor | telnet por prompt, HMP con OCR, teclas y texto | cubierto; consola interactiva llega con el carril CLI |

Los huecos concretos, con la prueba de que la ruta existe, están en
[API-COVERAGE.md](API-COVERAGE.md#endpoints-de-2261-que-este-repo-no-cubre).

## GNS3 3.x: no se declara soporte

Este cliente construye rutas `/v2` y autentica con Basic auth leída de
`~/.config/GNS3/2.2/gns3_server.conf`. GNS3 3.x usa `/v3`, login por token y otro esquema de
proyectos. **No hay servidor 3.x en este entorno para verificarlo** (2026-11-25), así que no se
declara compatibilidad: ni probada ni parcial.

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
- **`gns3lab snap restore` manda el nombre en la ruta donde la API espera `snapshot_id`.** El
  MCP `gns3_snapshots` sí resuelve el id por nombre. Para restaurar, usa el MCP o pasa el id.
- **Las capturas se guardan y se resumen, no se diseccionan.** Se descarga el `.pcap` y, si hay
  `tshark`, se muestran las primeras líneas; el análisis de paquetes es de `tshark`/Wireshark.

## Lo que este proyecto no es

- No es un cliente de GNS3 3.x.
- No sustituye al VNC para instaladores interactivos con ratón.
- No es un cliente completo de la API: la lista de lo que falta está en
  [API-COVERAGE.md](API-COVERAGE.md).
