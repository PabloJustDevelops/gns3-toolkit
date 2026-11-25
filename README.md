# gns3-toolkit

Operar un servidor **GNS3 2.2** desde la terminal o desde un agente MCP, sin GUI. Núcleo
compartido (`gns3core`), servidor MCP de 18 tools y CLI `gns3lab` con 23 subcomandos.

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
gns3lab shot PF1 -p examen-kit           # la pantalla del nodo, como texto
gns3lab exec PC1 "ip dhcp" "show ip" -p examen-kit
gns3lab -s clase port examen-kit --name "Pablo Rodriguez" --start
```

## Superficie

**CLI** — `servers status up down test export import fix port images templates snap exec shot
key type mon new node upload draw link doctor`. Referencia completa en
[docs/COMANDOS.md](docs/COMANDOS.md).

**MCP** — 18 tools: `gns3_status projects templates nodes links topology console capture
snapshots images node_files server_paths exec monitor node_edit upload drawings project_io`.
Transporte stdio; credenciales leídas de `~/.config/GNS3/2.2/gns3_server.conf`.

**Núcleo** — `Client` (REST `/v2`), `Console` (telnet por prompt, `--More--`, `[y/n]`,
`Password:`), `QemuMonitor` (HMP: `sendkey`, `screendump`, `system_reset`), `ocr`. Sin
dependencias de terceros: sirve con la stdlib; Pillow y tesseract mejoran la captura.

## Documentación

- [docs/COMANDOS.md](docs/COMANDOS.md) — los 23 subcomandos con sus flags y un ejemplo.
- [docs/EXAMEN.md](docs/EXAMEN.md) — guion del examen, paso a paso, con la salida que confirma.
- [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) — cómo encajan CLI, MCP y núcleo.
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — síntoma, causa y arreglo.

## Límites

- Sólo GNS3 **2.2.x** (API `/v2`). La 3.x usa `/v3` y login por token; este cliente no sirve.
- `upload`, `node disk` y todo lo que lee `/proc` (`shot`, `key`, `type`, `mon`) actúan sobre el
  compute **local**. En un servidor remoto, el disco tiene que estar ya allí.
- El puerto de consola no se puede fijar por `PUT` en un nodo: se fija en la plantilla.
- El OCR lee bien 720x400 con fuente VGA; no espera texto pequeño.
- La suite de tests sin servidor está en curso; hoy sólo hay un smoke del MCP que necesita el
  servidor real.

Proyecto y estado: [PROJECT.md](PROJECT.md). Reglas para agentes: [AGENTS.md](AGENTS.md).
