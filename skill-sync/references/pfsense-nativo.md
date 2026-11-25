# pfSense nativo (referencia corta)

**Nunca guardes la contraseña en el repo**, en un markdown ni en un commit. Sólo variables de
entorno; léela con `read -rs` si quieres evitar el historial de la shell.

```bash
read -rsp 'Contraseña de pfSense: ' PFSENSE_PASSWORD; echo
export PFSENSE_PASSWORD
# Opcionales, con valores por defecto: PFSENSE_HOST (192.168.1.1),
# PFSENSE_PORT (22022), PFSENSE_USER (admin).
```

Los comandos `gns3lab pf` y `pfsense.py` están **previstos en los carriles `pfcli`/`pfcore`**;
si `gns3lab pf --help` no los lista, usa el menú por monitor HMP y vuelve a intentarlo cuando
se fusionen. Guía completa: [docs/PFSENSE-NATIVO.md](../../docs/PFSENSE-NATIVO.md).

## Comandos exactos

```bash
gns3lab pf detect -p examen-kit --json          # e1000 -> em0/em1; virtio -> vtnet0/1; sin SSH
gns3lab pf assign --wan em0 --lan em1           # [--opt1 <if real>]
gns3lab pf ip em1 192.168.1.1 24                # [--gw ...]
gns3lab pf dhcp em1 192.168.1.100 192.168.1.200 # [--dns ...]
gns3lab pf rule pass --if lan --proto tcp --src any --dst any --port 80
gns3lab pf nat --if wan
gns3lab pf ssh --port 22022
gns3lab pf status                               # versión, ifconfig, reglas y rutas
```

`assign` usa los nombres que ve el invitado; con un disco `em0/em1`, pon el nodo en
`gns3lab node props PF1 -p examen-kit --set adapter_type=e1000` para salir del bucle
«interface mismatch». `rule` y `nat` insertan antes de cualquier `reject`; `config put` hace
backup de `config.xml` y recarga con `/etc/rc.reload_all`.

## Sin SSH todavía: monitor, nunca VNC

```bash
gns3lab shot PF1 -p examen-kit
gns3lab type PF1 "1" --enter -p examen-kit
gns3lab shot PF1 -p examen-kit
gns3lab type PF1 "8" --enter -p examen-kit
gns3lab type PF1 "easyrule pass opt1 any any any" --enter -p examen-kit
gns3lab shot PF1 -p examen-kit
```

`ret` no `enter`; `shift-<tecla>` para mayúsculas; comprueba el eco con `shot` antes del `ret`.
El VNC queda para el primer arranque sin SSH y para instaladores con ratón.

## Verificación

```bash
gns3lab pf status
gns3lab doctor examen-kit               # «sin hallazgos»
gns3lab exec PC1 "ip dhcp" "show ip" "ping 192.168.1.1" -p examen-kit --idle 4
```

La prueba es `0% packet loss` y una IP distinta de `0.0.0.0`. Errores literales y causas, en
[TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md); guion completo, en
[EXAMEN.md](../../docs/EXAMEN.md). Reglas de la skill, en [../SKILL.md](../SKILL.md).
