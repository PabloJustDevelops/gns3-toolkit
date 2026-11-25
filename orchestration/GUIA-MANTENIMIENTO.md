# Guía de mantenimiento e integración

Objetivo: que cualquier persona o agente pueda instalar, verificar, testear, documentar,
sincronizar la skill y publicar este repo sin depender de memoria de sesiones anteriores.
Las cifras y el estado del entorno se sacan de [scripts/verify.py](../scripts/verify.py) y
[scripts/install.sh](../scripts/install.sh); este documento no es la fuente de verdad.

Alcance: GNS3 **2.2.x** (API `/v2`), Python 3.12 en `.venv` y la skill delgada de
[skill-sync/](../skill-sync/README.md). GNS3 3.x no entra: usa `/v3` y login por token.

## Reparto de responsabilidades

| Rol | Hace | No hace |
|---|---|---|
| Implementador del worktree | Edita sólo los ficheros del brief, ejecuta los gates y deja un commit local con salida real. | Push, PR, deploy, tocar el checkout canónico ni la skill real. |
| Revisor | Lee el diff, busca regresiones, secretos y alcance extra. | Editar ficheros ni lanzar subagentes. |
| Owner (Pablo) | Decide el merge, publica y aplica la skill con backup. | Dar por bueno un cambio sin la salida de los gates. |
| Cualquiera | Reporta hallazgos y comandos ejecutados. | Silenciar un gate, borrar comprobaciones o inventar resultados. |

| Área | Ficheros | Validación principal |
|---|---|---|
| Núcleo | `gns3core.py` | `pytest` y `scripts/verify.py` |
| pfSense | `pfsense.py` | `tests/test_pfsense.py` |
| MCP | `gns3_mcp_server.py` | `tests/test_mcp_smoke.py`, `tests/test_mcp_resources.py` |
| CLI | `cli/gns3lab` | `tests/test_*.py`, `gns3lab --help` |
| Documentación | `README.md`, `PROJECT.md`, `AGENTS.md`, `docs/` | `scripts/verify.py` y `scripts/check-links.py` |
| Skill | `skill-sync/` | `diff`, `bash -n` y `gns3lab doctor` |
| Integración | `orchestration/`, `scripts/` | `scripts/verify.py` y `scripts/check-links.py` |

## Checklist de una tanda

- [ ] Estoy en el worktree y la rama del brief: `git status --short` vacío y `git log -1 --oneline` es la base acordada.
- [ ] `.venv/bin/python -V` dice 3.12 y las dependencias están instaladas.
- [ ] Los cambios se limitan a los ficheros del brief.
- [ ] `scripts/verify.py` termina en `OK: sin deriva` (exit 0).
- [ ] `scripts/check-links.py` termina en `OK: sin enlaces rotos` (exit 0).
- [ ] `pytest -q` termina en `N passed` (exit 0, sin fallos ni errores).
- [ ] `git diff --check` no encuentra espacios sobrantes.
- [ ] Commit local con mensaje en minúsculas; sin push ni PR.
- [ ] Informe con ficheros, comandos, exit codes y salida literal.

## 1. Instalar

```bash
cd ~/Proyectos/gns3-toolkit
./scripts/install.sh
```

El instalador es idempotente y hace, en este orden: crea `.venv` con Python 3.12 usando `uv`
si no existe, instala `fastmcp httpx pillow pytest`, enlaza `~/.local/bin/gns3lab`, compila los
tres ficheros de entrada, ejecuta `scripts/verify.py` como aviso y lista las tools del MCP.
Mensajes esperados: `→ instalando dependencias`, `→ CLI enlazada: ...`, `→ compila` y
`→ tools del MCP:` seguido del número real. Avisa si falta `uv` (aborta), `tesseract` (el OCR
queda vacío) o si hay deriva. `tesseract` y `qemu-img` son opcionales; `qemu-img` lo comprueba
`gns3lab doctor`.

Escribe el symlink en `~/.local/bin`, fuera del worktree: si el brief prohíbe instalar fuera,
no lo ejecutes y usa `.venv/bin/python` directamente. El venv nunca se commitea.

## 2. Verificar

### Deriva entre docs, código y skill

```bash
env -u PYTHONPATH -u VIRTUAL_ENV python3 scripts/verify.py
```

Salida real de esta sesión (los conteos cambian con el código; la línea que decide es la última):

```text
comandos=46 tools=42 áreas=12
OK: sin deriva
```

Exit code 0. Las cifras salen del AST (`handlers`, `@mcp.tool`, `API_V2_MAP`), no de constantes
escritas a mano. Si aparece `DRIFT`, cada línea trae `fichero:línea` y el valor declarado frente
al real. Corrige el documento o el código; no borres la comprobación. Un fichero obligatorio
ausente devuelve exit code 2 con `ERROR: ...`.

### Enlaces relativos

```bash
python3 scripts/check-links.py
```

Salida esperada:

```text
OK: sin enlaces rotos
```

Exit code 0. Recorre todos los `.md` del repo salvo `.git`, `.venv` y `__pycache__`; ignora
URLs absolutas, anclas puras y enlaces dentro de bloques de código. Si hay rotos, imprime
`ruta:línea: enlace roto: destino`, resume con `ROTO: N hallazgos` y devuelve exit code 1.
Se puede apuntar a otro árbol pasando la raíz como argumento.

### Sintaxis

```bash
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile \
  gns3core.py pfsense.py gns3_mcp_server.py cli/gns3lab \
  scripts/verify.py scripts/check-links.py
bash -n scripts/install.sh
bash -n skill-sync/scripts/gns3.sh
```

Los cuatro comandos deben devolver exit code 0 y no imprimir nada. Compilar con `.venv/bin/python`
comprueba el intérprete real (3.12); el `python3` del sistema puede ser más nuevo.

## 3. Testear

```bash
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q
```

Es la suite completa y no necesita servidor GNS3. Salida real de esta sesión:

```text
638 passed in 214.71s (0:03:34)
```

El número de tests crece con el repo; lo que decide es `passed`, sin `failed` ni `error`, y
exit code 0. Para una sola área, añade el fichero: `pytest -q tests/test_drift.py`. Si hay un
fallo, pega la salida literal y el nombre del test; no lo marques como `skip` ni relajes la
aserción.

Cobertura, cuando toque justificarla:

```bash
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q \
  --cov=gns3core --cov=pfsense --cov-report=term-missing --cov-fail-under=98
```

El umbral y el estado real están en `PROJECT.md`; no copies un porcentaje de una sesión vieja.

## 4. Documentar

1. Recuenta antes de escribir cifras: `scripts/verify.py`, `gns3lab --help` y
   `mcp.list_tools()`. No pegues listas de tools ni comandos de otra sesión.
2. Comprueba los enlaces con `scripts/check-links.py`.
3. No escribas credenciales ni tokens, ni siquiera de ejemplo. Los placeholders permitidos son
   `changeme`, `todo`, `xxx` y `placeholder`; el servidor lee sus credenciales en ejecución de
   `~/.config/GNS3/2.2/gns3_server.conf`.
4. Las secciones históricas se marcan con un encabezado que contenga `hito`, `bitácora`,
   `tanda`, `pasada` o `históri`: `verify.py` no contrasta sus cifras porque describen su momento.
   No uses esas palabras para esquivar una cifra actual.
5. Si añades un comando o una tool, actualiza su documentación en el mismo cambio y ejecuta los
   gates otra vez.

## 5. Sincronizar la skill con backup

`skill-sync/` es la fuente; la skill instalada en `~/.hermes/skills/devops/gns3-lab-automation/`
es el destino. No edites la skill real a mano ni copies su contenido al repo. El procedimiento
completo y el de restauración están en [skill-sync/README.md](../skill-sync/README.md).

Resumen:

```bash
SKILL_DIR="$HOME/.hermes/skills/devops/gns3-lab-automation"
BK="$HOME/.hermes/backups/gns3-lab-automation-$(date +%Y%m%d-%H%M%S).tar.gz"
mkdir -p "$(dirname "$BK")"
tar -C "$(dirname "$SKILL_DIR")" -czf "$BK" "$(basename "$SKILL_DIR")"
test -s "$BK" && tar -tzf "$BK" | grep -q '/SKILL.md$' && echo "backup OK"
```

Debe imprimir `backup OK`. El backup va a `~/.hermes/backups/`, no a `/tmp`. Copia sólo después
de que los gates del repo pasen:

```bash
install -Dm644 skill-sync/SKILL.md "$SKILL_DIR/SKILL.md"
install -Dm755 skill-sync/scripts/gns3.sh "$SKILL_DIR/scripts/gns3.sh"
install -Dm644 skill-sync/references/pfsense-nativo.md \
  "$SKILL_DIR/references/pfsense-nativo.md"
diff -u skill-sync/SKILL.md "$SKILL_DIR/SKILL.md"
diff -u skill-sync/scripts/gns3.sh "$SKILL_DIR/scripts/gns3.sh"
diff -u skill-sync/references/pfsense-nativo.md \
  "$SKILL_DIR/references/pfsense-nativo.md"
bash -n "$SKILL_DIR/scripts/gns3.sh"
test -x "$SKILL_DIR/scripts/gns3.sh" && echo "envoltorio ejecutable"
```

Los `diff` deben salir vacíos. Después, `gns3lab doctor` (debe terminar en `sin hallazgos`) y
`hermes mcp test gns3` (debe contestar `Connected`). Si la copia sale mal, restaura el backup
según el README antes de seguir.

## 6. Publicar

Publicar es decisión del owner y requiere orden explícita. Un agente no hace push, PR, release
ni deploy. Antes de pedirlo, deja el trabajo revisable:

```bash
git log --oneline <base>..HEAD
git diff --stat <base>..HEAD
git status --short
```

El árbol debe estar limpio después del commit local y el diff debe contener sólo los ficheros
acordados. El push, si se autoriza, se hace desde el checkout canónico con la identidad del repo
(`PabloJustDevelops <pabloroga6@gmail.com>`), nunca con `-c` ni desde un worktree ajeno.

## Gates antes de merge

Ejecutar en este orden y guardar la salida:

```bash
cd /home/pablorg/Proyectos/gns3-toolkit.gk7-integ
env -u PYTHONPATH -u VIRTUAL_ENV python3 scripts/verify.py
python3 scripts/check-links.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q
bash -n scripts/install.sh skill-sync/scripts/gns3.sh
git diff --check
git status --short
```

Criterio: exit code 0 en los cinco primeros, `OK: sin deriva`, `OK: sin enlaces rotos`,
`N passed`, y en `git status --short` sólo los ficheros del brief. No hay merge con un gate en
rojo ni con un `DRIFT` justificado como «ya estaba».

## Qué NO tocar

En la tanda `gk7-integ` están prohibidos `gns3core.py`, `pfsense.py`, `gns3_mcp_server.py`,
`cli/gns3lab`, `tests/**`, `docs/**`, `README.md`, `AGENTS.md`, `PROJECT.md` y `.github/**`.
Sólo se tocan `orchestration/GUIA-MANTENIMIENTO.md`, `scripts/check-links.py`,
`skill-sync/README.md` y, si hay un fallo reproducible, `scripts/verify.py` o
`scripts/install.sh`.

Reglas permanentes:

- **VNC es el último recurso.** Primero consola telnet (`gns3lab exec`), después monitor HMP
  (`shot`/`type`/`key`); VNC sólo para instaladores con ratón.
- **Ningún secreto** en el repo, en un markdown, en un commit ni en el historial de la shell.
- **No cambies estado del servidor** (arrancar/parar nodos, `systemctl start libvirtd`, borrar
  proyectos, subir discos) sin reportarlo en el informe.
- **No silencies gates**: ni `|| true`, ni tests con `skip`, ni asserts relajados, ni quitar
  comprobaciones de `verify.py` para obtener verde.
- **No mezcles tandas**: un commit por etapa lógica, mensaje en minúsculas y sin push.
- **No edites la skill real** desde el repo ni copies su contenido aquí.

## Fallos de entorno frecuentes

| Síntoma | Causa | Acción |
|---|---|---|
| `ModuleNotFoundError` al ejecutar la CLI | `.venv` incompleto | `./scripts/install.sh` |
| `pytest` no encuentra tests | Ejecutado fuera de la raíz | `cd` al repo y repetir |
| `verify.py` devuelve 2 | Falta un fichero obligatorio | Revisar `OBLIGATORIOS` y el mensaje `ERROR:` |
| `doctor` devuelve 1 | `libvirtd` parado, proyecto cerrado o nodo sin arrancar | Leer el resumen; arrancar sólo lo que autorice el brief y reportarlo |
| `check-links.py` marca un enlace | Ruta relativa mal escrita o fichero renombrado | Corregir la ruta; no excluir el fichero |
| `python3` y `.venv` discrepan | El sistema usa otra versión de Python | Usar `.venv/bin/python` y `env -u PYTHONPATH -u VIRTUAL_ENV` |
