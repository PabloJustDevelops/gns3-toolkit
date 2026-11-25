# BRIEF — carril `skillres` (skill delgada apuntando al repo público)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-skillres` · rama `opencode/skillres`.

## Contexto

La skill de GNS3 en `~/.hermes/skills/devops/gns3-lab-automation/` tiene scripts propios
(`pfssh.py`, `pfweb.py`, `vpcs-console.py`, `vnc-menu.sh`) que duplican lo que ya hace `gns3lab`.
El repo acaba de publicarse en **`https://github.com/PabloJustDevelops/gns3-toolkit`**.
Hay que dejar una versión de la skill que no duplique lógica.

**No edites la skill real desde el worktree** (está fuera del repo y otro proceso podría usarla).
Entrega los ficheros listos en `skill-sync/` dentro del repo; el padre los aplicará:

- `skill-sync/SKILL.md` — versión nueva de la skill. Debe:
  - apuntar al repo público y a `scripts/install.sh`;
  - decir que herramientas y comandos se **recuentan desde el código** (`mcp.list_tools()` y
    `gns3lab --help`), no se copian de una sesión anterior;
  - conservar las reglas duras del `AGENTS.md` del repo (VNC último recurso, sin secretos,
    verificar con salida real, sólo 2.2.x) y las trampas ya pagadas;
  - quitar la sección de scripts duplicados y sustituirla por ejemplos de `gns3lab`.
- `skill-sync/scripts/gns3.sh` — envoltorio delgado que invoca `gns3lab` con el PATH correcto
  (`~/Proyectos/gns3-toolkit/cli/gns3lab`), sin lógica propia.
- `skill-sync/README.md` — instrucciones de instalación de la skill (copiar `SKILL.md` y el
  script a `~/.hermes/skills/devops/gns3-lab-automation/`) y verificación:
  `gns3lab doctor` y `hermes mcp test gns3`.

Lee `AGENTS.md`, `PROJECT.md`, `README.md`, `docs/COMANDOS.md` y la skill real en solo lectura.

## Reglas

Nada inventado: los comandos que nombres deben existir en `cli/gns3lab`. El envoltorio no debe
contener credenciales ni rutas de otros usuarios. Enlaces relativos válidos dentro de `skill-sync/`.

## Prohibido

No edites `gns3core.py`, `gns3_mcp_server.py`, `cli/gns3lab`, `tests/`, `docs/`, `README.md` ni
`PROJECT.md` del repo. No toques `~/.hermes/skills/`. No `git push`, no PR, no cambio de rama.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-skillres
bash -n skill-sync/scripts/gns3.sh && echo "shell OK"
grep -c 'gns3lab' skill-sync/SKILL.md
python3 - <<'EOF'
import pathlib, re
bad=[]
for md in pathlib.Path("skill-sync").glob("*.md"):
    for link in re.findall(r"\]\((?!http)([^)#]+)", md.read_text()):
        if not (md.parent/link).exists(): bad.append(f"{md}: {link}")
print("enlaces rotos:", bad or "ninguno")
EOF
```

Commit: `docs(skill): skill delgada apuntando al repo público`. Informa de ficheros y gates.
