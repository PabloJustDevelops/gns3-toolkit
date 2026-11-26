# hermes en este repo

Manda el `AGENTS.md` de la raíz; esto sólo añade cómo se arranca desde Hermes Agent.

- Headless: `hermes chat -q "<brief>" --oneshot`. `-z "<prompt>"` es el atajo de una sola consulta.
- En una TTY, `chat -q` siembra una sesión interactiva; sin `--oneshot` no termina solo. `--resume
  latest` reanuda y `--worktree` aísla el trabajo.
- `--yolo` sólo en un worktree desechable y con el brief por delante; no cambia el estado del
  servidor GNS3 sin reportarlo.
- MCP: `hermes mcp add gns3 --command "$(pwd)/.venv/bin/python" --args
  "$(pwd)/gns3_mcp_server.py"`.
- Este repo no asume que Hermes cargue `PROJECT.md`, `STATUS.md` ni skills propias: el contexto
  compartido es el `AGENTS.md` de la raíz.
- Verifica con los gates del `AGENTS.md` raíz y pega la salida.
