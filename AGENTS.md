# gns3-toolkit — reglas para agentes

Herramientas para operar un servidor **GNS3 2.2.x** desde la terminal o desde un agente MCP,
sin depender de la GUI ni del VNC. Nace de un examen real: montar pfSense, VLANs y NAT a
mano por VNC cuesta 40 minutos y pierde teclas.

## Qué es cada pieza

| Fichero | Qué hace |
|---|---|
| `gns3core.py` | Núcleo sin dependencias de terceros: `Client` (API REST v2), `Console` (consola telnet leída por prompt), `QemuMonitor` (canal HMP), `ocr`. |
| `gns3_mcp_server.py` | Servidor MCP (fastmcp) con 18 tools. Importa `gns3core`. |
| `cli/gns3lab` | CLI de 22 comandos. Añade la raíz del repo a `sys.path` e importa `gns3core`. |
| `tests/` | pytest: consola contra un servidor telnet falso, HMP falso, utilidades, y un smoke del MCP. |

## Reglas duras

- **El VNC es el último recurso.** Consola telnet primero (`exec`), monitor HMP después
  (`shot`/`type`/`key`). Si escribes `vncdotool` o abres Remmina sin haber probado `gns3lab shot`,
  estás haciendo el trabajo mal.
- **Nunca escribas un secreto** en el repo, en un markdown ni en un commit. Las credenciales del
  servidor se leen de `~/.config/GNS3/2.2/gns3_server.conf` en tiempo de ejecución.
- **No cambies estado fuera de la sesión sin decirlo**: arrancar/parar nodos, `systemctl start
  libvirtd`, borrar un proyecto o subir un disco se reportan en el informe final.
- **Verifica con salida real.** Un `200 OK` de la API no prueba nada: `gns3lab doctor`, un `ping`
  con `0% packet loss` o un `shot` con OCR son la prueba. Si algo falla, pega el error literal.
- **Compatibilidad**: sólo GNS3 **2.2.x**. La 3.x usa `/v3` con login por token y este cliente no sirve.
- **Python 3.12**, venv en `.venv/` (creado con `uv venv`). El venv **no** se commitea.

## Cómo se ejecuta

```bash
./scripts/install.sh                 # venv + deps + symlinks (idempotente)
gns3lab doctor                       # ¿está todo en pie?
source .venv/bin/activate            # para trabajar en el código
pytest -q                            # los tests no necesitan servidor GNS3
python -m py_compile gns3core.py gns3_mcp_server.py cli/gns3lab
```

El MCP se registra en Hermes con:

```bash
hermes mcp add gns3 --command ~/Proyectos/gns3-toolkit/.venv/bin/python \
  --args ~/Proyectos/gns3-toolkit/gns3_mcp_server.py
```

## Convenciones de código

- Español en comentarios y mensajes de usuario; inglés en nombres de funciones y variables.
- `gns3core.py` **no** puede importar `fastmcp` ni `httpx`: lo usa la CLI, que debe funcionar con
  la stdlib y Pillow opcional.
- Toda función que hable con el servidor devuelve datos, no imprime. Imprimir es cosa de `cli/`.
- Los errores de la API se presentan con el mensaje interno, no con el volcado de schema anidado
  (`gns3lab._err`).
- Un `tesseract` ausente degrada el OCR a cadena vacía, nunca rompe la captura.

## Trampas ya pagadas (no repetirlas)

- `screendump /ruta/x.png` escribe un **PPM** con extensión `.png`.
- OCR a escala x1 confunde `w` con `u`; usar x2 y `--psm 4`.
- `sendkey ret`, no `enter`. `shift-<tecla>` para mayúsculas y símbolos.
- La consola del invitado duerme: mandar `sendkey shift` antes de la primera tecla útil.
- `POST /templates/{id}` exige `compute_id: local` en el body o devuelve 404.
- `ports_mapping` exige `port_number` en todas las entradas.
- `POST /nodes/{id}/files/{ruta}` graba el body **en crudo**, no un JSON con `content`.
- pfSense con `em0/em1` en el `config.xml` y `adapter_type: virtio-net-pci` entra en bucle de
  «interface mismatch»: se arregla con `--set adapter_type=e1000`.
