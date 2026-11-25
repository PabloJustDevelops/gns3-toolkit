# Instalar la skill `gns3-lab-automation`

Esta carpeta contiene la versión delgada de la skill: apunta al repo público
**https://github.com/PabloJustDevelops/gns3-toolkit** y no duplica lógica. No edites la skill
instalada directamente desde un worktree; copia estos ficheros cuando el cambio esté listo.

## Ficheros

- [SKILL.md](SKILL.md) — definición y reglas de la skill.
- [scripts/gns3.sh](scripts/gns3.sh) — envoltorio que invoca `gns3lab` con
  `$HOME/Proyectos/gns3-toolkit/cli` primero en el PATH. Es un `exec`, sin lógica ni secretos.
- [references/pfsense-nativo.md](references/pfsense-nativo.md) — referencia corta del flujo
  nativo de pfSense (`pf detect` → `assign` → `ip` → `dhcp` → `rule` → `nat` → `ssh`). Aviso:
  nunca guardes la contraseña en el repo.

## Instalación

1. Clona o actualiza el repo y ejecuta su instalador (idempotente):

   ```bash
   git clone https://github.com/PabloJustDevelops/gns3-toolkit.git ~/Proyectos/gns3-toolkit
   cd ~/Proyectos/gns3-toolkit && ./scripts/install.sh
   ```

2. Copia los tres ficheros a la skill de Hermes:

   ```bash
   mkdir -p ~/.hermes/skills/devops/gns3-lab-automation/scripts \
            ~/.hermes/skills/devops/gns3-lab-automation/references
   cp skill-sync/SKILL.md ~/.hermes/skills/devops/gns3-lab-automation/SKILL.md
   cp skill-sync/scripts/gns3.sh ~/.hermes/skills/devops/gns3-lab-automation/scripts/gns3.sh
   cp skill-sync/references/pfsense-nativo.md \
      ~/.hermes/skills/devops/gns3-lab-automation/references/pfsense-nativo.md
   chmod +x ~/.hermes/skills/devops/gns3-lab-automation/scripts/gns3.sh
   ```

   Si la skill ya tenía scripts propios (`pfssh.py`, `pfweb.py`, `vpcs-console.py`,
   `vnc-menu.sh`, `pfsense-web.py`), bórralos: sus funciones las cubre `gns3lab`.

3. Registra el MCP si aún no está dado de alta:

   ```bash
   hermes mcp add gns3 --command "$HOME/Proyectos/gns3-toolkit/.venv/bin/python" \
     --args "$HOME/Proyectos/gns3-toolkit/gns3_mcp_server.py"
   ```

## Verificación

```bash
bash -n ~/.hermes/skills/devops/gns3-lab-automation/scripts/gns3.sh
gns3lab doctor
hermes mcp test gns3
```

`gns3lab doctor` debe terminar con `sin hallazgos`. `hermes mcp test gns3` debe contestar
`Connected` y descubrir las tools; el número se recuenta con `mcp.list_tools()` (o con el listado
que imprime `scripts/install.sh`), no se copia de aquí. En la CLI, `gns3lab --help` da la lista de
subcomandos vigente.

La skill sólo sirve para GNS3 **2.2.x** (API `/v2`). Las credenciales se leen en tiempo de
ejecución de `~/.config/GNS3/2.2/gns3_server.conf`: no se copian ni se escriben en la skill.
