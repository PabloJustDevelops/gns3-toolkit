# Harnesses compatibles

Este repo se puede lanzar desde Command Code, OpenCode, Hermes Agent, freebuff y Codex sin
instalar nada en el setup de otra persona. La compatibilidad vive en el repo: `AGENTS.md` en la
raíz para las reglas, un `AGENTS.md` corto por harness en `harnesses/`, y un detector que dice qué
hay instalado y con qué versión.

Ningún harness se ha arrancado en sesión real para escribir este documento: los comandos y los
límites salen de `--help`, `--version` y del detector. Lo que no está verificado se marca como
tal.

## Matriz

Versiones leídas el 2026-11-26 con `scripts/harness_detect.py --json` en este equipo.

| Harness | Versión | Comando canónico desde la raíz | Modo | Límite principal |
|---|---|---|---|---|
| [cmdc](../harnesses/cmdc/AGENTS.md) | 1.93.3 | `cmdc -p "<brief>" --yolo` | headless con `-p`; TUI sin `-p` | el alta de MCP stdio no está documentada en `mcp add --help` |
| [opencode](../harnesses/opencode/AGENTS.md) | 2.4.1 | `opencode run --auto --file brief.md "ejecuta el brief"` | headless con `run`; TUI con `opencode .` | `run` usa el servidor de fondo salvo `--standalone` |
| [hermes](../harnesses/hermes/AGENTS.md) | 0.23.4 | `hermes chat -q "<brief>" --oneshot` | headless con `-q --oneshot`; TUI con `chat` | `-q` en TTY siembra sesión interactiva si falta `--oneshot` |
| [freebuff](../harnesses/freebuff/AGENTS.md) | 0.2.38 | `freebuff --cwd .` | sólo TUI/MCP: **sin modo headless** | no existen `-p`/`--print`; no hay subcomando MCP |
| [codex](../harnesses/codex/AGENTS.md) | 0.172.0 | `codex exec "<brief>"` | headless con `exec`; TUI sin subcomando | el sandbox por defecto puede impedir escrituras |

`Versión` es el primer `X.Y.Z` de la primera línea de `--version`; el prefijo (`opencode v`,
`codex-cli`) se descarta.

## Detección

```bash
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python scripts/harness_detect.py --json
```

Devuelve un objeto con `harnesses` (una ficha por harness en el orden de la tabla, con `harness`,
`path`, `version`, `command`, `headless` y `notes`), `missing` y `exit_code`. Sale con 0 si están
los cinco y con 1 si falta alguno. Un timeout o una versión ilegible se anotan en `notes` y no
cambian el código de salida: el detector informa, no bloquea.

No usa red, no instala nada y no ejecuta prompts: sólo `shutil.which` y `<binario> --version` con
un timeout de 5 s.

## Cómo se carga `AGENTS.md`

El `AGENTS.md` de la raíz es el único fichero de contexto que este toolkit da por compartido: no se asume que lean `PROJECT.md` ni skills de Hermes. Cada harness descubre los ficheros de contexto según su versión; no se ha arrancado ninguno para verificarlo.

Los `harnesses/<nombre>/AGENTS.md` son reglas cortas para trabajar dentro de ese subdirectorio.
Si tu versión no los descubre al cambiar de directorio, pásalos explícitamente en el prompt o con
la opción de fichero del harness; no hay una opción común verificada para los cinco.

## MCP `gns3`

Sólo se publica la línea que `--help` permite construir. El servidor se lanza con el Python del
venv del repo:

```bash
# OpenCode
opencode mcp add gns3 -- "$(pwd)/.venv/bin/python" "$(pwd)/gns3_mcp_server.py"

# Hermes
hermes mcp add gns3 --command "$(pwd)/.venv/bin/python" --args "$(pwd)/gns3_mcp_server.py"

# Codex
codex mcp add gns3 -- "$(pwd)/.venv/bin/python" "$(pwd)/gns3_mcp_server.py"
```

- **cmdc**: `cmdc mcp add`, `add-json`, `list` y `get` existen (verificado con `--help`), pero
  `mcp add` sólo documenta `<name> [url]` y no dice dónde va el comando de un servidor stdio. No
  se inventa la línea: lee `cmdc mcp add --help` en tu versión antes de registrar nada.
- **freebuff**: no expone subcomando `mcp`. Su `--help` dice que `--trust-agents` carga los
  ficheros `.agents` del repo y `mcp.json` sin preguntar; este repo no trae ese fichero, así que
  no hay alta de MCP verificada para freebuff.
- Ninguno de los cinco se ha conectado al MCP `gns3` en esta tarea; el registro es configuración
  local y no se ejecuta aquí.

## WebUI de pfSense desde el host

La WebUI del firewall no está en la red del host, así que no se abre por IP. Cualquier harness
puede levantar la misma puerta local por nombre, en primer plano o en segundo plano:

```bash
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python scripts/pf_webui_proxy.py \
  examples/pf-perfiles/ --port 8080
# http://127.0.0.1:8080/pfsense-ejemplo-a/
# http://127.0.0.1:8080/pfsense-ejemplo-b/
```

Cada ruta sale de `pfsense.webui_name` y `pfsense.pfsense_ip` del YAML; los dos ejemplos usan
subredes distintas y no llevan credenciales. Un nombre desconocido da `404` y un redirect a otro
host no se sigue (`502`). El certificado autofirmado se acepta sólo en este proxy de laboratorio.

La WebUI del controller GNS3 es otra cosa: `GET /v2/servers` responde `404` con el controller
2.2.61 y la lista de servidores de la UI queda vacía. Para configurar pfSense sigue mandando la
consola telnet (`gns3lab exec`, `gns3lab type`, `gns3lab key`) y los comandos `gns3lab pf`; el VNC
es el último recurso.

## Límites reales

- **freebuff no tiene modo headless.** Su `--help` no lista `-p` ni `--print`; cualquier trabajo
  hay que hacerlo en la TUI. `--cwd`, `--continue` y `--trust-agents` sí están.
- **cmdc** usa `-p/--print` para headless, `--output-format json` para NDJSON y `-w/--worktree`
  para un worktree aislado. `--tools-all` habilita herramientas que un run headless retiene.
- **opencode** separa TUI (`opencode <dir>`) y headless (`opencode run`). `--worktree` crea un
  worktree y `--archived` deja la sesión fuera de los listados, útil en CI.
- **hermes** tiene dos atajos headless: `hermes chat -q "<prompt>" --oneshot` y `hermes -z
  "<prompt>"`. `--resume latest` reanuda y `--worktree` aísla.
- **codex** usa `codex exec` para headless, `codex exec resume` para continuar y `codex mcp` para
  servidores. El sandbox y las aprobaciones se configuran en Codex (consulta `codex exec --help`);
  un `exec` que no puede escribir debe reportarse, no saltarse con flags a ciegas.
- Ninguno sustituye a `gns3lab`: el toolkit se opera con la CLI o el MCP, no con la GUI ni el VNC.
  Las reglas duras están en el `AGENTS.md` de la raíz.

## Gates del repo

Cualquier harness que edite este repo ejecuta, desde la raíz:

```bash
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q
env -u PYTHONPATH -u VIRTUAL_ENV python3 scripts/verify.py
python3 scripts/check-links.py
```

Los tests no necesitan servidor GNS3. Un harness que no pueda ejecutar estos comandos debe decir
cuál falló y por qué, no dar el cambio por bueno.
