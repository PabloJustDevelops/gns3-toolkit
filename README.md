# gns3-toolkit

Operar un servidor **GNS3 2.2** desde la terminal o desde un agente MCP, sin GUI. Núcleo
compartido (`gns3core`, **12 áreas** en `API_V2_MAP`), servidor MCP de **49 tools** y CLI
`gns3lab` con **48 subcomandos**. Repo público:
https://github.com/PabloJustDevelops/gns3-toolkit

Estado real (2026-11-25), leído del código: **12 áreas** (`gns3core.API_V2_MAP`), **49 tools**
(`mcp.list_tools()` sobre `gns3_mcp_server.py`), **48 subcomandos** (`handlers` en
`cli/gns3lab`). Las
acciones de la GUI operativa portadas al núcleo están en
[docs/GUI-PORTADA.md](docs/GUI-PORTADA.md); las que aún no tienen comando o tool se marcan
«en curso» en ese documento.

Nace de un examen: montar pfSense, VLANs y NAT a mano por VNC cuesta 40 minutos y pierde
teclas. Aquí cada nodo se maneja por donde responde:

| Nodo | Vía | Comando |
|---|---|---|
| consola telnet (VPCS, IOU, Linux) | `Console`, lee por prompt o quietud | `gns3lab exec` |
| QEMU gráfico (pfSense, OpenWrt) | canal HMP de QEMU + OCR del framebuffer | `gns3lab shot/type/key` |
| instalador con ratón | VNC | Remmina |

## Instalación

```bash
./scripts/install.sh && gns3lab doctor
```

Crea el venv con Python 3.12, instala `fastmcp`, `httpx`, `pillow` y `pytest`, enlaza la CLI en
`~/.local/bin` y compila los tres ficheros. Requiere `uv`; `tesseract` y `qemu-img` son
opcionales (`doctor` dice si faltan).

Para registrar el MCP en Hermes:

```bash
hermes mcp add gns3 --command <repo>/.venv/bin/python --args <repo>/gns3_mcp_server.py
```

## Cinco comandos

```bash
gns3lab servers                          # qué servidores hay y si responden
gns3lab doctor examen-kit                # servidor, computes, libvirt, discos, NAT, monitores
gns3lab doctor --check-updates           # lo anterior + aviso de versión nueva (sin instalar nada)
gns3lab shot PF1 -p examen-kit           # la pantalla del nodo, como texto
gns3lab exec PC1 "ip dhcp" "show ip" -p examen-kit
gns3lab -s clase port examen-kit --name "Pablo Rodriguez" --start
gns3lab pf detect -p examen-kit --json       # wan=em0, lan=em1 sin SSH
```

## Superficie

**CLI** — 48 subcomandos: `servers status up down test export import fix port compute stats
symbols appliances images templates snap template console capture exec shot key type mon new
node upload draw link doctor project notify symbol iou-license server emulator nio capture-port
all disk vm watch verify`. Referencia completa en [docs/COMANDOS.md](docs/COMANDOS.md).

**MCP** — 49 tools: `gns3_appliances gns3_batch gns3_capture gns3_command_line gns3_compute gns3_compute_endpoint gns3_compute_download gns3_console
gns3_console_control gns3_drawing_get gns3_drawings gns3_emulator gns3_events gns3_events_url gns3_exec
gns3_gns3vm gns3_images gns3_iou_license gns3_link_edit gns3_link_get gns3_links gns3_monitor gns3_nio
gns3_node_action gns3_node_edit gns3_node_files gns3_nodes gns3_nodes_bulk gns3_notifications
gns3_port_capture gns3_project_file_list gns3_project_files gns3_project_io gns3_project_stats gns3_projects
gns3_server gns3_server_paths gns3_snapshots gns3_statistics gns3_status gns3_symbols
gns3_template gns3_templates gns3_topology gns3_upload gns3_verify`. Transporte stdio; credenciales leídas
de `~/.config/GNS3/2.2/gns3_server.conf`.

**Núcleo** — `Client` (REST `/v2`), `Console` (telnet por prompt, `--More--`, `[y/n]`,
`Password:`), `QemuMonitor` (HMP: `sendkey`, `screendump`, `system_reset`), `ocr`. Sin
dependencias de terceros: sirve con la stdlib; Pillow y tesseract mejoran la captura.

## Documentación

- [docs/API-COVERAGE.md](docs/API-COVERAGE.md) — las 12 áreas de la API v2, endpoint a endpoint:
  método del núcleo, verbo CLI, tool MCP, test, rutas sin puente agrupadas por handler y lo que
  GNS3 2.2.61 expone y no se cubre.
- [docs/GUI-PORTADA.md](docs/GUI-PORTADA.md) — lo que hacías en la GUI → comando → tool MCP →
  método del núcleo → endpoint, con las acciones aún «en curso».
- [docs/NIO-Y-CAPTURAS.md](docs/NIO-Y-CAPTURAS.md) — captura de enlace frente a captura por
  puerto, body del NIO y qué significa un `500` del compute.
- [docs/EVENTOS.md](docs/EVENTOS.md) — URLs WebSocket, eventos según los handlers y estado real
  del cliente (stream HTTP sí, WS en curso).
- [docs/LIMITES-CONTROLLER-COMPUTE.md](docs/LIMITES-CONTROLLER-COMPUTE.md) — qué rutas son del
  controller, cuáles se reenvían al compute, por qué hay `409` sin VirtualBox/VMware y por qué
  existe `/v1/version` pero no `/v2/controller`.
- [docs/COMPATIBILIDAD.md](docs/COMPATIBILIDAD.md) — qué significa «compatibilidad total», por
  qué GNS3 3.x no se declara soportado y los límites reales.
- [docs/PARIDAD.md](docs/PARIDAD.md) — operación a operación, qué hay en CLI y qué en MCP.
- [docs/COMANDOS.md](docs/COMANDOS.md) — los subcomandos con sus flags y un ejemplo.
- [docs/EXAMEN.md](docs/EXAMEN.md) — guion del examen, paso a paso, con la salida que confirma.
- [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) — cómo encajan CLI, MCP y núcleo.
- [docs/PFSENSE-NATIVO.md](docs/PFSENSE-NATIVO.md) — integración nativa sin VNC: detección de
  interfaces, `config.xml`, reglas/NAT/SSH, errores literales y verificación.
- [docs/VERIFICACION.md](docs/VERIFICACION.md) — `gns3lab verify` y `gns3_verify`: checks por
  componente, salida estructurada y límites de la comprobación (solo lectura).
- [docs/HARNESSES.md](docs/HARNESSES.md) — lanzar el repo desde Command Code, OpenCode, Hermes,
  freebuff o Codex: comandos, MCP y límites reales.
- [docs/LAB-SPEC.md](docs/LAB-SPEC.md) — laboratorio declarativo en YAML: `validate`, `plan`,
  `apply --yes` y `verify`.
- [docs/UPDATES.md](docs/UPDATES.md) — versión local y comprobación de actualizaciones sin auto-upgrade.
- [orchestration/COMPONENTES-CANDIDATOS.md](orchestration/COMPONENTES-CANDIDATOS.md) — inventario
  vivo de endpoints y candidatos a portar.
- [docs/MCP-VELOCIDAD.md](docs/MCP-VELOCIDAD.md) — `gns3_batch`, paralelismo de lecturas y
  medición real del coste del MCP.
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — síntoma, causa y arreglo.

## Límites

- Sólo GNS3 **2.2.x** (API `/v2`). La 3.x usa `/v3` y login por token; este cliente no sirve.
  Detalle en [docs/COMPATIBILIDAD.md](docs/COMPATIBILIDAD.md).
- `upload`, `node disk` y todo lo que lee `/proc` (`shot`, `key`, `type`, `mon`) actúan sobre el
  compute **local**. En un servidor remoto, el disco tiene que estar ya allí.
- El puerto de consola no se puede fijar por `PUT` en un nodo: se fija en la plantilla.
Declaración de alcance: 12 áreas, 49 tools y 48 comandos, recalculados por `scripts/verify.py`.
- El OCR lee bien 720x400 con fuente VGA; no espera texto pequeño.
- Tests: 764 passed, cobertura 100 % de `gns3core.py` (996 sentencias, 0 miss) y 100 % de
  `pfsense.py` (435 sentencias, 0 miss), con dobles
  de HTTP, telnet y HMP y sin servidor GNS3. La matriz de lo que cubre cada
  endpoint está en [docs/API-COVERAGE.md](docs/API-COVERAGE.md).

Proyecto y estado: [PROJECT.md](PROJECT.md). Reglas para agentes: [AGENTS.md](AGENTS.md).
