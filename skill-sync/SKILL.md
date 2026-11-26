---
name: gns3-lab-automation
description: "Use when driving GNS3 2.2 labs from Hermes or extending the toolkit."
version: 2.3.0
author: Hermes (Pablo)
license: MIT
metadata:
  hermes:
    tags: [gns3, networking, mcp, labs]
    related_skills: [libvirt-vm-management, docker-management]
---

# GNS3 desde Hermes

La automatización vive en un único repo público:
**https://github.com/PabloJustDevelops/gns3-toolkit**. Esta skill no trae scripts propios:
toda la lógica está en `gns3core.py`, `cli/gns3lab` y `gns3_mcp_server.py`. Si algo que
necesitas no existe, se añade allí, no se reescribe aquí.

## Cuándo usarla

Crear, arrancar, configurar o verificar laboratorios GNS3 2.2.x desde Hermes: topologías,
consolas, capturas, snapshots, imágenes y plantillas, o portar un lab al servidor del aula.

## Instalación

```bash
git clone https://github.com/PabloJustDevelops/gns3-toolkit.git ~/Proyectos/gns3-toolkit
cd ~/Proyectos/gns3-toolkit && ./scripts/install.sh && gns3lab doctor
```

`scripts/install.sh` es idempotente: crea el venv con Python 3.12 (`uv`), instala
`fastmcp httpx pillow pytest pytest-cov pyyaml`, enlaza `~/.local/bin/gns3lab`, compila los tres ficheros y
lista las tools del MCP. `tesseract` y `qemu-img` son opcionales; `doctor` dice si faltan.
El venv no se commitea. Para registrar el MCP en Hermes:

```bash
hermes mcp add gns3 --command "$HOME/Proyectos/gns3-toolkit/.venv/bin/python" \
  --args "$HOME/Proyectos/gns3-toolkit/gns3_mcp_server.py"
```

Para invocar la CLI desde cualquier sitio, el envoltorio delgado de esta skill es
[scripts/gns3.sh](scripts/gns3.sh): fija el PATH a `~/Proyectos/gns3-toolkit/cli` y hace
`exec gns3lab "$@"`. No añade nada.

## La superficie se recuenta desde el código, nunca se copia

El número de comandos, tools y áreas cambia por oleadas. Antes de declararlo, recuéntalo:

```bash
gns3lab --help                          # subcomandos
gns3lab <subcomando> --help             # flags de ese subcomando
cd ~/Proyectos/gns3-toolkit && env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python - <<'EOF'
import asyncio, sys
sys.path.insert(0, ".")
import gns3_mcp_server as s
print(len(asyncio.run(s.mcp.list_tools())))
EOF
# áreas de la API v2: len(gns3core.API_V2_MAP)
```

No pegues la lista de tools ni la de comandos de una sesión anterior: puede estar desactualizada.
La referencia completa y versionada está en el repo:
[docs/COMANDOS.md](https://github.com/PabloJustDevelops/gns3-toolkit/blob/master/docs/COMANDOS.md),
[docs/PARIDAD.md](https://github.com/PabloJustDevelops/gns3-toolkit/blob/master/docs/PARIDAD.md) y
[docs/API-COVERAGE.md](https://github.com/PabloJustDevelops/gns3-toolkit/blob/master/docs/API-COVERAGE.md).

## Reglas duras (del `AGENTS.md` del repo)

- **El VNC es el último recurso.** Consola telnet primero (`gns3lab exec`), monitor HMP después
  (`shot`/`type`/`key`/`mon`). Si escribes `vncdotool` o abres Remmina sin haber probado
  `gns3lab shot`, estás haciendo el trabajo mal. El VNC queda para instaladores con ratón.
- **Nunca escribas un secreto** en el repo, en un markdown ni en un commit. Las credenciales del
  servidor se leen de `~/.config/GNS3/2.2/gns3_server.conf` en tiempo de ejecución.
- **No cambies estado fuera de la sesión sin decirlo**: arrancar/parar nodos,
  `systemctl start libvirtd`, borrar un proyecto o subir un disco se reportan en el informe final.
- **Verifica con salida real.** Un `200 OK` de la API no prueba nada: `gns3lab doctor`, un `ping`
  con `0% packet loss` o un `shot` con OCR son la prueba. Si algo falla, pega el error literal.
- **Compatibilidad**: sólo GNS3 **2.2.x** (API `/v2`). La 3.x usa `/v3` con login por token y este
  cliente no sirve. Detalle en
  [docs/COMPATIBILIDAD.md](https://github.com/PabloJustDevelops/gns3-toolkit/blob/master/docs/COMPATIBILIDAD.md).
- Convenciones del código: `gns3core.py` no importa `fastmcp` ni `httpx`; las funciones que hablan
  con el servidor devuelven datos, imprime sólo `cli/`; los errores se muestran con el mensaje
  interno, no con el schema anidado; sin `tesseract`, el OCR queda como cadena vacía y la captura
  sigue funcionando.

## Ejemplos con `gns3lab` (en lugar de scripts propios)

```bash
gns3lab servers                              # servidores y si responden
gns3lab status examen-kit                    # proyectos, nodos, puertos de consola
gns3lab doctor examen-kit                    # barrido antes de tocar nada
gns3lab up examen-kit                        # abre y arranca los nodos

gns3lab exec PC1 "ip dhcp" "show ip" -p examen-kit --idle 4
gns3lab exec R1 "show ip route" --expect '# $' -p examen-kit
gns3lab shot PF1 -p examen-kit               # framebuffer + OCR (x2, --psm 4)
gns3lab type PF1 "2" --enter -p examen-kit   # opción de menú
gns3lab key PF1 down down ret --show -p examen-kit
gns3lab mon PF1 info status -p examen-kit    # HMP crudo
gns3lab test examen-kit                      # PC↔PC, PC→gateway, PC→8.8.8.8
gns3lab verify qemu examen-kit --node PF1    # checks de solo lectura del nodo
gns3lab doctor --check-updates --json        # ¿hay versión nueva?
gns3lab project ls -p examen-kit --prefix project-files/ --json
gns3lab compute endpoint local --emulator qemu --remote-action binaries --json
gns3lab compute download local --emulator qemu --remote-action binaries --out pcap.bin
python3 scripts/labspec.py validate examples/lab-ejemplo.yaml
python3 scripts/labspec.py plan examples/lab-ejemplo.yaml

gns3lab node props PF1 --set adapter_type=e1000 --set ram=2048 -p examen-kit
gns3lab link add PC1 SW1 --pa 0 --pb 0 --ppb 1 -p examen-kit
gns3lab snap create antes-de-tocar examen-kit
gns3lab -s clase port examen-kit --from local --name "Pablo Rodriguez" --start
```

La consola telnet lee por prompt o quietud y responde sólo a `--More--`, `[y/n]` y `Password:`.
En nodos QEMU, `shot` usa el monitor HMP: el puerto se localiza leyendo `/proc/*/cmdline`
(`gns3core.find_monitor_port`), nunca se adivina. Para verificar de verdad, `ping -c 2 <ip>`
y `0% packet loss`; con VPCS, la IP se pone por consola (`ip dhcp`) y se confirma con `show ip`.

## Verificación por componente y laboratorio declarativo

`gns3lab verify <qemu|pf|vpcs> <proyecto>` y el tool `gns3_verify` comprueban estado real sin
abrir proyectos ni arrancar nodos: `/proc` + HMP en QEMU, `config.xml` y entorno en pfSense,
`show ip` en VPCS. Devuelve `{component, project, ok, checks, problems}`; con `--json` es
parseable. No valida tráfico real ni sustituye a `doctor`. Detalle:
[docs/VERIFICACION.md](https://github.com/PabloJustDevelops/gns3-toolkit/blob/master/docs/VERIFICACION.md).

`scripts/labspec.py` describe el laboratorio en YAML (`version`, `project`, `nodes`, `links`,
`expect`) y ofrece `validate`, `plan`, `apply --yes` y `verify`. `plan` no escribe; `apply`
usa sólo comandos existentes de la CLI. No borra proyectos ni nodos. Detalle:
[docs/LAB-SPEC.md](https://github.com/PabloJustDevelops/gns3-toolkit/blob/master/docs/LAB-SPEC.md).

`gns3lab --version` imprime la versión local. `gns3lab doctor --check-updates [--json]` consulta
GitHub con caché de 24 h (`GNS3LAB_NO_UPDATE_CHECK=1` la desactiva), nunca auto-actualiza. Si
no hay release ni tag, reporta `update_available: false` sin error. Detalle:
[docs/UPDATES.md](https://github.com/PabloJustDevelops/gns3-toolkit/blob/master/docs/UPDATES.md).

`gns3lab project ls` lista ficheros del proyecto en un compute (`--compute`, por defecto `local`),
con `--prefix` opcional; `gns3_compute_endpoint` y `gns3lab compute endpoint ...` resuelven la URL
directa del compute. `gns3_compute_download` y `gns3lab compute download ... --out RUTA [--force]`
bajan los bytes de esa URL a un temporal del directorio de destino y hacen rename atómico: sin
`--force` rechazan sobrescribir. No lances una descarga real sin que el usuario lo pida. Para
lanzar el repo desde cinco harness distintos, consulta `docs/HARNESSES.md` y
`scripts/harness_detect.py --json`.

## Trampas ya pagadas (no repetirlas)

- `screendump /ruta/x.png` escribe un **PPM** con extensión `.png`; el núcleo lo convierte.
- OCR a escala x1 confunde `w` con `u`; usar x2 y `--psm 4`.
- `sendkey ret`, no `enter`. `shift-<tecla>` para mayúsculas y símbolos.
- La consola del invitado duerme: mandar `sendkey shift` antes de la primera tecla útil y
  comprobar el eco con `shot` antes del `ret`.
- `POST /templates/{id}` exige `compute_id: local` en el body o devuelve 404.
- `ports_mapping` exige `port_number` en todas las entradas.
- `POST /nodes/{id}/files/{ruta}` graba el body **en crudo**, no un JSON con `content`.
- pfSense con `em0/em1` en el `config.xml` y `adapter_type: virtio-net-pci` entra en bucle de
  «interface mismatch»: se arregla con `--set adapter_type=e1000`.

Detalle y casos límite (snapshots con nodos parados, capturas, `PUT` parcial de nodo, gateway de
VPCS, persistencia en el `.gns3`, GUI en Wayland) en los docs del repo:
[docs/TROUBLESHOOTING.md](https://github.com/PabloJustDevelops/gns3-toolkit/blob/master/docs/TROUBLESHOOTING.md),
[docs/EXAMEN.md](https://github.com/PabloJustDevelops/gns3-toolkit/blob/master/docs/EXAMEN.md) y
[docs/ARQUITECTURA.md](https://github.com/PabloJustDevelops/gns3-toolkit/blob/master/docs/ARQUITECTURA.md).
