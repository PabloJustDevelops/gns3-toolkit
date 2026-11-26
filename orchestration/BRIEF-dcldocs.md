# BRIEF — carril `dcldocs` (documentación declarativa y skill)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-dcldocs` · rama `opencode/dcldocs`.

## Contexto

Lee `AGENTS.md`, `PROJECT.md`, `docs/LAB-SPEC.md` (72 líneas, esquema v1 ya documentado),
`docs/COMANDOS.md`, `docs/INDEX.md`, `docs/MCP-VELOCIDAD.md`, `skill-sync/README.md` y los
briefs `BRIEF-dclcore.md`, `BRIEF-dclcli.md`, `BRIEF-dclmcp.md`. Los otros carriles están
añadiendo `export`, `diff`, `plan` idempotente, `gns3lab lab` y los resources/tool del lab.

## Qué entregar (solo en el repo, no toques la skill real)

1. **`docs/LAB-DECLARATIVO.md`**: guía del ciclo completo
   `validate → export → diff → apply --yes → verify`, con ejemplos reales de comandos y salida
   de ejemplo **marcada como ejemplo** (nunca presentarla como salida medida). Explica que
   `sobrantes` solo se informan, nunca se borran, y que `apply` sin `--yes` sale con 2.
2. Actualizar **`docs/LAB-SPEC.md`**: añadir las dos claves nuevas (`export`, `diff`) y el
   subcomando `gns3lab lab`, sin borrar lo que ya está. Aclarar que `ip` sigue siendo solo
   expectativa de verificación.
3. **`skill-sync/references/lab-declarativo.md`**: versión corta para la skill con los seis
   comandos, la variable `GNS3_LAB_SPEC` y la regla de no borrar nada. Añadirlo a la lista de
   ficheros de `skill-sync/README.md`.
4. **`docs/COMANDOS.md` y `docs/INDEX.md`**: añadir `lab` y los tres resources nuevos con
   enlaces relativos válidos.

## Reglas

Verifica cada comando contra `cli/gns3lab` y cada tool contra `gns3_mcp_server.py`. Si algo
está aún en otro carril, márcalo como «previsto en el carril dclcore/dclcli/dclmcp», no como
hecho. Español, sin relleno, sin cifras que no estén medidas. Enlaces relativos válidos.

## Prohibido

No edites `gns3core.py`, `scripts/labspec.py`, `gns3_mcp_server.py`, `cli/gns3lab`, `tests/`,
`AGENTS.md` ni `PROJECT.md`. No toques `~/.hermes/skills/`. No `git push`, no PR, no cambio
de rama.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-dcldocs
python3 scripts/check-links.py
python3 - <<'EOF'
import pathlib, re
for md in [pathlib.Path("docs/LAB-DECLARATIVO.md"), pathlib.Path("docs/LAB-SPEC.md"),
           pathlib.Path("skill-sync/references/lab-declarativo.md")]:
    print(md, md.exists(), len(md.read_text()) if md.exists() else 0)
EOF
```

Commit: `docs: ciclo declarativo export/diff/apply y reference de skill`. Informa de gates.
