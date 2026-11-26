# opencode en este repo

Manda el `AGENTS.md` de la raíz; esto sólo añade cómo se arranca desde OpenCode.

- Headless: `opencode run --auto --file brief.md "ejecuta el brief"`; TUI: `opencode .`.
- `--format json` da la respuesta en JSON; `--archived` evita que una sesión de CI aparezca en los
  listados; `--worktree` la abre en un worktree nuevo.
- `--auto` aprueba permisos no denegados explícitamente. No lo uses para escrituras fuera del
  repo ni para tocar el servidor GNS3 sin decirlo.
- MCP: `opencode mcp add gns3 -- "$(pwd)/.venv/bin/python" "$(pwd)/gns3_mcp_server.py"`.
- El `AGENTS.md` del subdirectorio se descubre al trabajar en él; si no aparece, dilo en vez de
  suponer que se ha cargado.
- Verifica con los gates del `AGENTS.md` raíz y pega la salida.
