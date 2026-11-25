# BRIEF — carril `pfskill` (portar la integración nativa a la skill)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-pfskill` · rama `opencode/pfskill`.

## Contexto

La skill `gns3-lab-automation` ya es delgada (apunta al repo público). Falta enseñar el flujo
nativo de pfSense para que otras personas no se queden en el VNC. Lee `AGENTS.md`, `PROJECT.md`,
`README.md`, `docs/EXAMEN.md`, `docs/TROUBLESHOOTING.md`, `skill-sync/SKILL.md` y el contrato de
`pfsense.py` en `orchestration/BRIEF-pfcore.md`.

## Qué entregar (solo en el repo; no toques la skill real)

1. **`docs/PFSENSE-NATIVO.md`**: guía paso a paso del flujo nativo:
   - `gns3lab pf detect -p <proyecto>` para saber si el disco usa `em0/em1` o `vtnet0/1`;
   - por qué `adapter_type=e1000` evita el bucle «interface mismatch»;
   -variables de entorno para SSH (nombres, nunca valores);
   - `pf assign` → `pf ip` → `pf dhcp` → `pf rule` → `pf nat` → `pf ssh`;
   - cuándo hace falta todavía el menú (solo primer arranque sin SSH) y cómo hacerlo con
     `gns3lab type/key` del monitor, no con VNC;
   - verificación con `pf status`, `gns3lab doctor` y ping desde un VPCS con `--idle 4`.
   Incluye una tabla de errores literales y su causa (sin inventar salidas).
2. **`skill-sync/references/pfsense-nativo.md`**: versión corta de la guía para la skill,
   con los comandos exactos y un aviso de «nunca guardes la contraseña en el repo».
3. **`skill-sync/README.md`**: añade el reference nuevo a la lista de ficheros a copiar.
4. **`docs/MCP-VELOCIDAD.md`**: explica `gns3_batch` (operaciones paralelas de solo lectura,
   orden de resultados por índice, cache opcional) y cómo medirlo con el comando del gate del
   carril `pfmcp`. Sin prometer cifras que no estén medidas en el código.

## Reglas

Nada inventado: verifica cada comando en `cli/gns3lab` y cada tool en `gns3_mcp_server.py`
(pueden estar en mitad del cambio; si algo no existe, márcalo como «previsto en el carril pfcli/
pfmcp»). Enlaces relativos válidos. Español, sin relleno.

## Prohibido

No edites `gns3core.py`, `pfsense.py`, `gns3_mcp_server.py`, `cli/gns3lab`, `tests/`,
`AGENTS.md` ni `PROJECT.md`. No toques la skill real en `~/.hermes/skills/`. No `git push`,
no PR, no cambio de rama.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-pfskill
python3 - <<'EOF'
import pathlib, re
bad=[]
for md in list(pathlib.Path("docs").glob("*.md"))+list(pathlib.Path("skill-sync").rglob("*.md")):
    for link in re.findall(r"\]\((?!http)([^)#]+)", md.read_text()):
        if not (md.parent/link).exists(): bad.append(f"{md}: {link}")
print("enlaces rotos:", bad or "ninguno")
EOF
grep -c 'gns3lab pf' docs/PFSENSE-NATIVO.md
```

Commit: `docs: flujo pfSense nativo y velocidad del MCP`. Informa de ficheros y gates.
