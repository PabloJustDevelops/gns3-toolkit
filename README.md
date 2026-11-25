# gns3-toolkit

Operar un servidor **GNS3 2.2** desde la terminal y desde un agente: núcleo compartido,
servidor MCP (18 tools) y CLI `gns3lab` (22 comandos). Sin GUI, y con el VNC sólo como
último recurso.

## Por qué existe

Montar un escenario de examen (pfSense, VLANs, NAT, clientes) por la consola VNC cuesta
40 minutos y pierde teclas: la primera tras un rato sin actividad se la come el invitado.
Aquí cada nodo se maneja por donde sí responde:

| Nodo | Vía | Comando |
|---|---|---|
| consola telnet (VPCS, IOU, Linux) | `Console`, lee por prompt o quietud | `gns3lab exec` |
| QEMU gráfico (pfSense, OpenWrt) | canal HMP + OCR del framebuffer | `gns3lab shot/type/key` |
| instalador con ratón | VNC | Remmina |

## Instalación

```bash
./scripts/install.sh          # venv + dependencias + symlink de la CLI
gns3lab doctor                # comprueba servidor, computes, libvirt, tesseract, discos
```

Requiere Python 3.12, `uv`, y opcionalmente `tesseract` y `qemu-img`.

## Uso rápido

```bash
gns3lab status                         # proyectos y nodos
gns3lab doctor examen-kit              # chequeo integral
gns3lab shot pfSense -p examen-kit     # la pantalla del nodo, en texto
gns3lab type pfSense "2" --enter       # opción de menú sin VNC
gns3lab exec PC1 "ip dhcp" "show ip"   # consola telnet limpia
gns3lab node switch SW1 --port 1=access:20 --port 0=dot1q:43
gns3lab link add PF1 SW1 --pa 1 --pb 0 --ppb 0
gns3lab up examen-kit
```

## Superficie

**CLI** — `servers status up down test fix export import port images templates snap exec shot
key type mon new node link upload draw doctor`

**MCP** — `gns3_status projects templates nodes links topology console capture snapshots images
node_files server_paths exec monitor node_edit upload drawings project_io`

**Núcleo** — `Client` (REST v2), `Console` (telnet por prompt/quietud), `QemuMonitor` (HMP:
sendkey, screendump, reset), `ocr`, utilidades de fichero de nodo.

## Tests

```bash
pytest -q        # no necesitan servidor GNS3
```

## Límites

- Sólo GNS3 **2.2.x** (`/v2`). La 3.x usa login por token y este cliente no sirve.
- `upload` y `clone_disk` actúan sobre el compute local.
- El OCR lee 720x400 (fuente VGA); no espera texto de 8 px.
