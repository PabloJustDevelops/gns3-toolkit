# Sincronizar la skill `gns3-lab-automation`

Esta carpeta es la copia versionada de la skill delgada. No contiene lógica propia: apunta al
repo público **https://github.com/PabloJustDevelops/gns3-toolkit**, y toda la implementación
vive en `gns3core.py`, `cli/gns3lab` y `gns3_mcp_server.py`. La skill instalada en
`~/.hermes/skills/devops/gns3-lab-automation/` es un destino, no una fuente: se actualiza
copiando desde aquí y **nunca** editando el repo desde la skill.

## Ficheros

- [SKILL.md](SKILL.md) — definición y reglas de la skill.
- [scripts/gns3.sh](scripts/gns3.sh) — envoltorio que pone `$HOME/Proyectos/gns3-toolkit/cli`
  primero en el PATH y hace `exec gns3lab "$@"`. Sin lógica ni credenciales.
- [references/pfsense-nativo.md](references/pfsense-nativo.md) — referencia corta del flujo
  nativo de pfSense (`pf detect` → `assign` → `ip` → `dhcp` → `rule` → `nat` → `ssh`).
  Aviso: nunca guardes la contraseña en el repo.
- [references/lab-declarativo.md](references/lab-declarativo.md) — referencia corta del ciclo
  `validate → export → diff → apply --yes → verify`, la variable `GNS3_LAB_SPEC` y la regla de
  no borrar los `sobrantes`. Previsto en los carriles `dclcore`/`dclcli`/`dclmcp`.
- [references/capturas-fases.md](references/capturas-fases.md) — referencia corta del ciclo de
  capturas por fase: HMP para consola, WebUI sólo para evidencia y en modo lectura, VNC último
  recurso, credenciales del entorno e `indice.md` sin documento final. Piezas previstas en
  `capcore`/`capweb`/`capmcp`.

## Instalación desde cero

1. Clona o actualiza el repo y ejecuta el instalador idempotente:

   ```bash
   git clone https://github.com/PabloJustDevelops/gns3-toolkit.git ~/Proyectos/gns3-toolkit
   cd ~/Proyectos/gns3-toolkit && ./scripts/install.sh
   ```

2. Registra el MCP si aún no está dado de alta:

   ```bash
   hermes mcp add gns3 --command "$HOME/Proyectos/gns3-toolkit/.venv/bin/python" \
     --args "$HOME/Proyectos/gns3-toolkit/gns3_mcp_server.py"
   ```

3. Si la skill todavía no existe, créala y copia los ficheros; si ya existe, usa el
   procedimiento con backup de la sección siguiente:

   ```bash
   SKILL_DIR="$HOME/.hermes/skills/devops/gns3-lab-automation"
   mkdir -p "$SKILL_DIR/scripts" "$SKILL_DIR/references"
   install -Dm644 skill-sync/SKILL.md "$SKILL_DIR/SKILL.md"
   install -Dm755 skill-sync/scripts/gns3.sh "$SKILL_DIR/scripts/gns3.sh"
   install -Dm644 skill-sync/references/pfsense-nativo.md \
     "$SKILL_DIR/references/pfsense-nativo.md"
   install -Dm644 skill-sync/references/lab-declarativo.md \
     "$SKILL_DIR/references/lab-declarativo.md"
   install -Dm644 skill-sync/references/capturas-fases.md \
     "$SKILL_DIR/references/capturas-fases.md"
   ```

## Sincronización con backup y verificación

`skill-sync/` es la fuente. La skill real sólo se toca cuando el cambio ya está commiteado en
el repo y los gates pasan. El backup va fuera del repo, en `~/.hermes/backups/`, no en `/tmp`:
`/tmp` se vacía y el respaldo se pierde.

1. Comprueba el repo antes de copiar:

   ```bash
   cd ~/Proyectos/gns3-toolkit
   env -u PYTHONPATH -u VIRTUAL_ENV python3 scripts/verify.py
   python3 scripts/check-links.py
   ```

   Deben terminar en `OK: sin deriva` y `OK: sin enlaces rotos`, con exit code 0.

2. Guarda un backup de la skill instalada:

   ```bash
   SKILL_DIR="$HOME/.hermes/skills/devops/gns3-lab-automation"
   BK="$HOME/.hermes/backups/gns3-lab-automation-$(date +%Y%m%d-%H%M%S).tar.gz"
   mkdir -p "$(dirname "$BK")"
   tar -C "$(dirname "$SKILL_DIR")" -czf "$BK" "$(basename "$SKILL_DIR")"
   test -s "$BK" && tar -tzf "$BK" | grep -q '/SKILL.md$' && echo "backup OK"
   ```

   Debe imprimir `backup OK`. Si el `tar` o la comprobación fallan, no sigas.

3. Copia los ficheros versionados (crea los directorios si faltan, conserva permisos):

   ```bash
   install -Dm644 skill-sync/SKILL.md \
     "$SKILL_DIR/SKILL.md"
   install -Dm755 skill-sync/scripts/gns3.sh \
     "$SKILL_DIR/scripts/gns3.sh"
   install -Dm644 skill-sync/references/pfsense-nativo.md \
     "$SKILL_DIR/references/pfsense-nativo.md"
   install -Dm644 skill-sync/references/lab-declarativo.md \
     "$SKILL_DIR/references/lab-declarativo.md"
   install -Dm644 skill-sync/references/capturas-fases.md \
     "$SKILL_DIR/references/capturas-fases.md"
   ```

4. Verifica que la copia es idéntica y que el envoltorio es válido:

   ```bash
   diff -u skill-sync/SKILL.md "$SKILL_DIR/SKILL.md"
   diff -u skill-sync/scripts/gns3.sh "$SKILL_DIR/scripts/gns3.sh"
   diff -u skill-sync/references/pfsense-nativo.md \
     "$SKILL_DIR/references/pfsense-nativo.md"
   diff -u skill-sync/references/lab-declarativo.md \
     "$SKILL_DIR/references/lab-declarativo.md"
   diff -u skill-sync/references/capturas-fases.md \
     "$SKILL_DIR/references/capturas-fases.md"
   bash -n "$SKILL_DIR/scripts/gns3.sh"
   test -x "$SKILL_DIR/scripts/gns3.sh" && echo "envoltorio ejecutable"
   ```

   Los cinco `diff` deben salir con exit code 0 y sin líneas.

5. Borra los scripts antiguos **sólo después del backup**, si siguen ahí. Sus funciones ya las
   cubre `gns3lab`:

   ```bash
   for f in pfssh.py pfweb.py pfsense-web.py vpcs-console.py vnc-menu.sh; do
     if [ -e "$SKILL_DIR/scripts/$f" ]; then rm -v "$SKILL_DIR/scripts/$f"; fi
   done
   ```

6. Comprueba la skill instalada:

   ```bash
   gns3lab doctor
   hermes mcp test gns3
   ```

   `gns3lab doctor` termina en `sin hallazgos` cuando el servidor, el proyecto, `libvirtd` y las
   herramientas están en orden; si falla, imprime cada problema y devuelve exit code 1.
   `hermes mcp test gns3` debe contestar `Connected` y descubrir las tools.

7. Si algo sale mal, restaura el backup: aparta la copia rota y extrae la anterior.

   ```bash
   mv "$SKILL_DIR" "$SKILL_DIR.roto-$(date +%Y%m%d-%H%M%S)"
   tar -C "$(dirname "$SKILL_DIR")" -xzf "$BK"
   ```

## Verificación rápida

```bash
bash -n ~/.hermes/skills/devops/gns3-lab-automation/scripts/gns3.sh
gns3lab doctor
hermes mcp test gns3
```

El número de tools y comandos se recuenta desde el código (`mcp.list_tools()`,
`gns3lab --help`, `scripts/verify.py`), nunca se copia de este README ni de una sesión anterior.
La skill sólo sirve para GNS3 **2.2.x** (API `/v2`). Las credenciales se leen en tiempo de
ejecución de `~/.config/GNS3/2.2/gns3_server.conf`: no se copian ni se escriben en la skill.
