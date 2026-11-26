# freebuff en este repo

Manda el `AGENTS.md` de la raíz; esto sólo añade cómo se arranca desde freebuff.

- **No hay modo headless**: `-p` y `--print` no existen en su `--help`. Todo el trabajo pasa por la
  TUI; no escribas scripts que asuman una salida no interactiva.
- Arranca con `freebuff --cwd .` desde la raíz. `--continue` retoma la conversación anterior.
- `--trust-agents` carga los ficheros `.agents` del repo y `mcp.json` sin preguntar. Úsalo sólo
  después de revisar qué hay en el repo; este repo no trae `.agents/mcp.json`.
- No hay subcomando `mcp` verificado: no inventes uno. Si hace falta el MCP `gns3`, regístralo
  desde otro harness o pide instrucciones antes.
- Verifica con los gates del `AGENTS.md` raíz y pega la salida.
