# BRIEF — carril `dclmcp` (resources de laboratorio y tool `gns3_lab`)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-dclmcp` · rama `opencode/dclmcp`.

## Contexto

Los resources actuales son `gns3://status`, `gns3://projects`, `gns3://templates` y el template
`gns3://project/{project}/topology` (ver `gns3_mcp_server.py` ≈3648). `scripts/labspec.py` ya
tiene validate/plan/apply/verify y el carril `dclcore` añade `export`/`diff` con el contrato de
`orchestration/BRIEF-dclcore.md`. Lee `AGENTS.md`, ese brief y `gns3_mcp_server.py`.

## Contrato

### Resources (JSON, con `_resource_json` existente)

- `gns3://lab/desired`: lee la ruta de la variable de entorno `GNS3_LAB_SPEC`. Si no está
  definida o el fichero no existe, devuelve `{"error": "...", "hint": "define GNS3_LAB_SPEC"}`;
  nunca inventa una ruta. Devuelve la spec validada y normalizada.
- `gns3://lab/actual`: obtiene la topología del proyecto declarado en `desired` reutilizando
  `gns3://project/{project}/topology` (o su helper). Devuelve la topología cruda resumida.
- `gns3://lab/diff`: llama a `labspec.diff(deseado, actual)` y añade el `plan` como órdenes
  legibles. Debe ser de solo lectura.

### Tool

`gns3_lab(action="validate|plan|diff|apply|export|verify", spec=None, topology=None,
project=None, out=None, yes=False, server=None) -> dict`:

- Delega **siempre** en `scripts/labspec.py`; no reimplementes validación ni diff.
- `apply` sin `yes=True` devuelve `{"ok": False, "error": "apply escribe en GNS3: ...",
  "plan": [...]}` y no toca nada. Con `yes=True` devuelve el resultado real, incluyendo
  el código de salida.
- `export` acepta `topology` como dict o fichero JSON; `project` se usa como nombre por defecto.
- Las acciones `validate`, `plan`, `diff` y `export(topology dado)` funcionan sin servidor.
- Errores literales con `error`; nunca una excepción sin manejar ni credenciales en la salida.

### Carga del módulo

Usa un helper tipo `_labspec_module()` con `importlib.util.spec_from_file_location` sobre
`Path(__file__).parent / "scripts" / "labspec.py"`, con caché en `sys.modules`, patrón ya usado
para `pfsense.py` (`_pfsense_module()` ≈502). Si el módulo falta, error claro.

## Prohibido

No edites `scripts/labspec.py`, `gns3core.py`, `cli/gns3lab`, `tests/`, `docs/`, `README.md`
ni `PROJECT.md`. No `git push`, no PR, no cambio de rama. No ejecutes `apply` con `yes=True`
contra un servidor real; verifica con `list_tools`, resources y `diff`.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-dclmcp
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile gns3_mcp_server.py
env -u PYTHONPATH -u VIRTUAL_ENV python3 - <<'EOF'
import asyncio, sys, os
sys.path.insert(0,".")
import gns3_mcp_server as s
print("tools:", len(asyncio.run(s.mcp.list_tools())))
print("resources:", [str(r.uri) for r in asyncio.run(s.mcp.list_resources())])
os.environ["GNS3_LAB_SPEC"]="examples/lab-ejemplo.yaml"
print("desired:", asyncio.run(s.mcp.read_resource("gns3://lab/desired"))[:1][0].text[:100])
topo={"project":"lab-ejemplo","nodes":[],"links":[]}
print("diff:", s.gns3_lab(action="diff", topology=topo))
print("apply sin yes:", s.gns3_lab(action="apply", spec="examples/lab-ejemplo.yaml"))
EOF
```

Commit: `feat(mcp): resources de laboratorio y tool gns3_lab`. Informa de salida real.
