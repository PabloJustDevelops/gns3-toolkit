# BRIEF — carril `covdocs` (matriz de cobertura y compatibilidad)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-covdocs` · rama `opencode/covdocs` (no cambies).

## Contexto

El repo opera GNS3 **2.2.x** por la API `/v2`. Hoy hay 20 tools MCP, 23 comandos CLI y
una cobertura de tests del 60 % sobre `gns3core.py`. Se están añadiendo, en paralelo:

- CLI (`opencode/cli`): `compute`, `stats`, `symbols`, `appliances`, `capture`, `console`,
  y nuevos verbos en `node`, `link`, `draw`, `snap`, `template`.
- MCP (`opencode/mcp`): `gns3_compute`, `gns3_statistics`, `gns3_symbols`,
  `gns3_appliances`, `gns3_node_action`, `gns3_command_line`, más `update` en
  `gns3_links`/`gns3_drawings` y `file_name` en `gns3_capture`.
- Tests (`opencode/tests`): 100 % de cobertura de `gns3core.py`.

`gns3core.API_V2_MAP` define las 8 áreas cubiertas. Lee `AGENTS.md`, `PROJECT.md`,
`gns3core.py`, `gns3_mcp_server.py`, `cli/gns3lab` (solo lectura) y la chuleta
`/home/pablorg/GNS3/CHULETA.md`.

## Qué entregar

1. **`docs/API-COVERAGE.md`** — una tabla por cada una de las 8 áreas de `API_V2_MAP`, con
   cuatro columnas: endpoint (literal del mapa), método de `gns3core`, comando/verbo CLI,
   tool/acción MCP, y test que lo cubre. Debajo, una lista explícita de **endpoints de la
   API v2 que GNS3 2.2.61 expone y este repo NO cubre**, si los hay (compruébalo con
   peticiones GET de solo lectura contra `http://127.0.0.1:3080`; no inventes).
2. **`docs/COMPATIBILIDAD.md`** — qué significa «compatibilidad total» aquí: la API v2
   completa para operar un laboratorio (proyectos, plantillas, nodos, enlaces, capturas,
   dibujos, snapshots, computes, imágenes, símbolos, appliances, consola y monitor).
   Un apartado honesto sobre **GNS3 3.x**: usa `/v3` con login por token y **no hay servidor
   3.x en este entorno para verificarlo**, así que no se declara soporte; solo se describe
   qué habría que cambiar (`base_url`, autenticación Bearer, esquema de proyectos).
   Y un apartado de límites reales: `upload`/`clone_disk` solo sobre compute local,
   `console` no se fija por PUT en el nodo, OCR a 720x400.
3. **`docs/PARIDAD.md`** — tabla operación → CLI → MCP → cubierto en tests, para que se vea
   de un vistazo si algo está solo en un lado. Incluye todas las tools nuevas y los comandos
   nuevos del contrato ( léelos de `orchestration/BRIEF-cli.md` y `BRIEF-mcp-paridad.md`).
4. Actualiza **`README.md`** con un enlace a los tres documentos y una línea de estado real:
   números de tools/comandos **leyéndolos del código**, no estimados.

## Reglas

- Nada inventado: si un flag, un comando o una tool no está en el código, no lo escribas.
- Los enlaces relativos entre documentos deben existir.
- Español, frases cortas, sin relleno.

## Prohibido

- **No edites** `gns3core.py`, `gns3_mcp_server.py`, `cli/gns3lab`, `tests/`, `AGENTS.md` ni
  `PROJECT.md`. No `git push`, no PR, no cambio de rama.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-covdocs
python3 - <<'EOF'
import pathlib, re
bad=[]
for md in pathlib.Path("docs").glob("*.md"):
    for link in re.findall(r"\]\((?!http)([^)#]+)", md.read_text()):
        if not (md.parent/link).exists() and not pathlib.Path(link).exists(): bad.append(f"{md}: {link}")
print("enlaces rotos:", bad or "ninguno")
EOF
grep -c '^|' docs/API-COVERAGE.md docs/PARIDAD.md
```

Commit en tu rama con mensaje `docs: matriz de cobertura API v2 y límites de compatibilidad`.
Informa de los ficheros, de los gates y de cualquier endpoint sin cubrir que encontraste.
