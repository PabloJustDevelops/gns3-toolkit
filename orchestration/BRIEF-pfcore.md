# BRIEF — carril `pfcore` (integración nativa con pfSense)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-pfcore` · rama `opencode/pfcore`.

## Contexto

El único punto débil del toolkit es configurar pfSense: hoy se hace por VNC/menú o por OCR del
monitor, y eso se rompe y cuesta tiempo a otras personas. La vía nativa es hablar el formato
que pfSense entiende de verdad: **`/conf/config.xml`** y sus comandos (`/etc/rc.reload_all`,
`pfctl`, `ifconfig`, `easyrule`), por SSH. `sshpass`, `qemu-nbd` y `tshark` están instalados;
no hay `guestfish`. Lee `AGENTS.md`, `PROJECT.md`, `gns3core.py`, `docs/EXAMEN.md` y
`docs/TROUBLESHOOTING.md`.

**Nunca escribas credenciales en el repo.** La contraseña se lee de variables de entorno.

## Contrato (API pública; los otros carriles programan contra ella)

Fichero nuevo `pfsense.py` en la raíz, sin dependencias de terceros:

```python
class PfSenseError(RuntimeError): ...

class PfSense:
    def __init__(self, host="192.168.1.1", user="admin", password=None, port=22022, timeout=20)
    @classmethod
    def from_env(cls)                 # PFSENSE_HOST / USER / PASSWORD / PORT (host y puerto con defaults)
    def run(self, cmd: str, timeout=None) -> dict   # {cmd, output, ok, error}; enmascara la password en output/error
    def status(self) -> dict          # versión, interfaces (ifconfig), reglas (pfctl -sr), rutas
    def get_config(self) -> dict      # lee /conf/config.xml y lo parsea con xml.etree -> dict
    def put_config(self, doc: dict, backup=True) -> dict
                                      # copia config.xml a config.xml.bak-<stamp>, escribe el XML
                                      # generado y ejecuta /etc/rc.reload_all; devuelve {ok, backup, detail}
    def interfaces(self) -> dict      # {wan:{if,ip,mask,dhcp}, lan:{...}, opt1:{...}}
    def assign(self, mapping: dict) -> dict
                                      # mapping {"wan":"em0","lan":"em1","opt1":None};
                                      # reescribe <interfaces> y evita el bucle "interface mismatch"
    def set_ip(self, ifname, ip, mask, gateway=None) -> dict
    def dhcp(self, ifname, start, end, dns=None) -> dict
    def rule(self, action="pass", ifname="lan", proto="any", src="any", dst="any", port=None) -> dict
    def nat(self, ifname="wan", target=None) -> dict
    def enable_ssh(self, port=22022) -> dict

def render_config(doc: dict) -> str     # XML válido para pfSense 2.7 ( pfSense <system>, <interfaces>, <dhcpd>, <filter>, <nat> )
def parse_config(xml: str) -> dict      # inverso; conserva las secciones que no entiende
def detect_ifnames(node: dict) -> dict  # em0/em1 si adapter_type=e1000; vtnet0/1 si virtio; desde properties del nodo
```

Requisitos:
- `run()` usa `sshpass -p … ssh -p N -o StrictHostKeyChecking=no …`, `capture_output=True`,
  `text=True`, `timeout`, y devuelve errores literales. Nunca imprime la contraseña.
- `put_config()` **nunca borra secciones desconocidas**: `parse_config` conserva el XML original
  y solo sustituye los nodos que se tocan.
- `assign()` comprueba que el nombre de interfaz existe en el sistema (`ifconfig`) antes de
  escribirlo; si no, devuelve error con los nombres disponibles en vez de inventar.
- `rule()` y `nat()` insertan reglas **antes** de cualquier `reject` existente (la lección ya
  pagada: el orden del array manda, no el `tracker`).
- `detect_ifnames()` lee `node["properties"]["adapter_type"]` y devuelve `{"wan":…,"lan":…}`.

## Prohibido

No edites `gns3core.py`, `gns3_mcp_server.py`, `cli/gns3lab`, `tests/`, `docs/`, `README.md` ni
`PROJECT.md`. No `git push`, no PR, no cambio de rama. **No ejecutes SSH contra pfSense real**:
las pruebas son con dobles.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-pfcore
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile pfsense.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python - <<'EOF'
import pfsense as pf
xml='<pfsense><system><hostname>fw</hostname></system><interfaces><wan><if>em0</if></wan><lan><if>em1</if></lan></interfaces><filter><rule><action>pass</action></rule></filter></pfsense>'
d=pf.parse_config(xml)
print('parse:', d.get('system',{}).get('hostname'), sorted(d.get('interfaces',{}).keys()))
out=pf.render_config(d)
print('render:', out.startswith('<pfsense>'), '<if>em0</if>' in out)
print('detect e1000:', pf.detect_ifnames({'properties':{'adapter_type':'e1000'}}))
print('detect virtio:', pf.detect_ifnames({'properties':{'adapter_type':'virtio-net-pci'}}))
EOF
```

Commit: `feat(pfsense): integración nativa por config.xml y SSH`. Informa de salida real.
