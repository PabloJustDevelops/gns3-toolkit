# BRIEF — carril `docs`

Eres un agente de coding. Trabajas SOLO en este worktree:

- Ruta: `/home/pablorg/Proyectos/gns3-toolkit-wt-docs`
- Rama: `opencode/docs` (ya creada, no cambies de rama)

## Contexto que no se infiere del código

Este repo empaqueta la operación de un GNS3 2.2 sin GUI: núcleo (`gns3core.py`), servidor MCP
de 18 tools y CLI `gns3lab` de 22 comandos. Nace de preparar un examen: montar pfSense, VLANs,
NAT y clientes a mano por VNC cuesta 40 minutos y pierde teclas.

Lee antes de escribir: `AGENTS.md`, `PROJECT.md`, `gns3core.py`, `gns3_mcp_server.py`,
`cli/gns3lab` (los tres últimos **solo lectura**), y la chuleta de referencia
`/home/pablorg/GNS3/CHULETA.md` (puedes citarla, no la modifiques).

## Qué tienes que entregar

1. **`docs/COMANDOS.md`** — referencia de los 22 comandos de `gns3lab`, en tabla o secciones:
   qué hace cada uno, sus flags reales (léelos del `add_argument`, no los inventes) y **un
   ejemplo ejecutable** por comando. Incluye los 12 nuevos (`exec`, `shot`, `type`, `key`,
   `mon`, `new`, `node`, `link`, `upload`, `draw`, `doctor` y el modo sin VNC).
2. **`docs/EXAMEN.md`** — guion operativo del examen, en orden: comprobar servidor, levantar el
   kit, leer el menú de pfSense por OCR, asignar interfaces, VLANs en el switch, verificar con
   `ping` y `doctor`, y llevarlo al servidor del aula. Cada paso con el comando exacto y **qué
   salida confirma que salió bien**.
3. **`docs/ARQUITECTURA.md`** — cómo encajan las tres piezas: un diagrama ASCII del flujo
   (CLI/MCP → `gns3core` → REST `/v2` del servidor → nodos), qué hace cada clase del núcleo, y
   por qué la consola se lee por prompt y el QEMU por HMP en vez de VNC.
4. **`README.md`** — reescríbelo corto y honesto: qué es, instalación de una línea, cinco
   comandos de ejemplo, superficie (CLI/MCP/núcleo), límites. Sin marketing, sin emojis de
   relleno, sin prometer lo que no hace (por ejemplo: no es compatible con GNS3 3.x).
5. **`docs/TROUBLESHOOTING.md`** — tabla síntoma → causa → arreglo, con las trampas ya pagadas:
   `screendump` que produce un PPM con nombre `.png`, OCR de `w` como `u`, `sendkey ret`,
   consola que duerme y se come la primera tecla, `compute_id: local` en templates,
   `port_number` obligatorio, `files` que graba el body en crudo, bucle de «interface mismatch»
   con `virtio` y `em0/em1`, `libvirtd` parado y NAT.

## Reglas

- **Nada inventado.** Si un flag o una salida no la puedes leer en el código, no la escribas.
  Ejecuta `gns3lab --help` y cada `gns3lab <cmd> --help` para copiar la sintaxis real.
- Todos los enlaces relativos entre documentos deben existir.
- Español, frases cortas, sin relleno ni superlativos.

## Prohibido

- **No edites** `gns3core.py`, `gns3_mcp_server.py`, `cli/gns3lab` ni `tests/`.
- No toques `AGENTS.md` ni `PROJECT.md` (son la fuente de verdad del proyecto).
- No `git push`, no PR. No cambies de rama.

## Gates (pega la salida real)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-docs
for c in $(gns3lab --help | sed -n 's/.*{\(.*\)}.*/\1/p' | tr ',' ' '); do
  echo "== $c"; gns3lab $c --help 2>&1 | head -3
done > /tmp/help-real.txt; wc -l /tmp/help-real.txt
grep -c '^## ' docs/COMANDOS.md
python3 - <<'EOF'
import pathlib, re
bad = []
for md in pathlib.Path("docs").glob("*.md"):
    for link in re.findall(r"\]\((?!http)([^)#]+)", md.read_text()):
        if not (md.parent / link).exists() and not pathlib.Path(link).exists():
            bad.append(f"{md}: {link}")
print("enlaces rotos:", bad or "ninguno")
EOF
```

## Entrega

Commit en tu rama, mensaje `docs: referencia de comandos, guion de examen y arquitectura`, y en
el informe: qué ficheros escribiste, salida de los gates, enlaces rotos (debe ser ninguno) y
cualquier afirmación que no pudiste verificar en el código.
