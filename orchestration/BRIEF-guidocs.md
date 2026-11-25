# BRIEF — carril `guidocs` (documentación de la GUI portada)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-guidocs` · rama `opencode/guidocs`.

## Contexto

`gns3core.API_V2_MAP` tiene ahora **11 áreas** (las 8 anteriores más `symbols`, `gui_admin` y
`emulators`). El inventario real de 78 rutas de `gns3server` está en
`orchestration/inventario-rutas-gns3.txt`. En paralelo se están añadiendo comandos CLI
(`BRIEF-guicli.md`) y tools MCP (`BRIEF-guimcp.md`) con contratos definidos ahí.

## Qué entregar

1. **`docs/GUI-PORTADA.md`**: tabla «lo que hacías en la GUI → comando → tool MCP → método del
   núcleo → endpoint». Cubre todas las operaciones de los dos briefs, sin inventar nombres.
2. **`docs/API-COVERAGE.md`**: actualízalo de 8 a **11 áreas** y añade un apartado con las rutas
   del inventario que siguen sin puente (agrupadas por handler), distinguiendo las que son
   internas de compute (nio, capturas por puerto) de las que sí son funcionalidad de usuario.
3. **`docs/COMPATIBILIDAD.md`**: añade una nota honesta: GNS3 3.x sigue sin declararse;
   `gns3server` 2.2.61 es Python legible en
   `~/Applications/gns3/venv/lib/python3.14/site-packages/gns3server/handlers`, y el inventario
   se extrajo de ahí, no de memoria.
4. Actualiza `README.md` con `docs/GUI-PORTADA.md` en el índice y los números reales de áreas,
   comandos y tools leyéndolos del código.

## Reglas

Nada inventado: verifica cada nombre en `gns3core.py`, `cli/gns3lab` y `gns3_mcp_server.py` (estos
dos últimos pueden estar en mitad del cambio; si algo aún no existe, márcalo como «en curso»
en vez de afirmarlo). Enlaces relativos válidos. Español, sin relleno.

## Prohibido

No edites `gns3core.py`, `gns3_mcp_server.py`, `cli/gns3lab`, `tests/`, `AGENTS.md` ni
`PROJECT.md`. No `git push`, no PR, no cambio de rama.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-guidocs
python3 - <<'EOF'
import pathlib, re
bad=[]
for md in pathlib.Path("docs").glob("*.md"):
    for link in re.findall(r"\]\((?!http)([^)#]+)", md.read_text()):
        if not (md.parent/link).exists() and not pathlib.Path(link).exists(): bad.append(f"{md}: {link}")
print("enlaces rotos:", bad or "ninguno")
EOF
grep -c '^|' docs/GUI-PORTADA.md docs/API-COVERAGE.md
```

Commit: `docs: GUI portada a CLI/MCP e inventario de 78 rutas`. Informa de ficheros y gates.
