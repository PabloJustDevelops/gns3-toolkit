# codex en este repo

Manda el `AGENTS.md` de la raíz; esto sólo añade cómo se arranca desde Codex.

- Headless: `codex exec "<brief>"`; sin subcomando abre la TUI. `codex exec resume` continúa una
  sesión anterior.
- El sandbox y las aprobaciones salen de tu configuración. Si `exec` no puede escribir, no lo
  fuerces con un flag a ciegas: reporta el bloqueo y el comando exacto que falló.
- MCP: `codex mcp add gns3 -- "$(pwd)/.venv/bin/python" "$(pwd)/gns3_mcp_server.py"`.
- Este repo comparte contexto por `AGENTS.md`; no des por hecho que Codex lee otros ficheros del
  repo que no hayas comprobado.
- Verifica con los gates del `AGENTS.md` raíz y pega la salida.
