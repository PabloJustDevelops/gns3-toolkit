# cmdc en este repo

Manda el `AGENTS.md` de la raíz; esto sólo añade cómo se arranca desde Command Code.

- Desde la raíz: `cmdc -p "<brief>" --yolo` para headless; `cmdc` sin `-p` abre la TUI.
- `--output-format json` da NDJSON; `-w` crea un worktree aislado antes de trabajar.
- `--tools-all` habilita herramientas que un run headless retiene: úsalo con criterio, no para
  saltarte permisos en escrituras destructivas.
- `cmdc mcp add`, `add-json`, `list` y `get` existen, pero el `--help` no documenta el comando de
  un servidor MCP stdio. No inventes la línea: comprueba `cmdc mcp add --help` en tu versión.
- Verifica con los gates del `AGENTS.md` raíz y pega la salida; un `200 OK` no es prueba.
