# BRIEF — carril `capmcp` (tool MCP de capturas)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-capmcp` · rama `opencode/capmcp`.

## Contexto

Los carriles `capcore` y `capweb` añaden `captures.py` (HMP + índice) y `webui_capture.py`
(navegador headless). Lee `AGENTS.md`, `gns3_mcp_server.py` (patrón `_pfsense_module()`,
`gns3_pfsense`, `_resource_json`) y los briefs `BRIEF-capcore.md`, `BRIEF-capweb.md`.

## Contrato

Una tool nueva:

```python
gns3_capturas(action="phases|console|webui|index", project=None, spec=None,
              node=None, outdir=None, phase=None) -> dict
```

- `phases`: devuelve `captures.phases_from_spec(spec)` (o la spec apuntada por
  `GNS3_LAB_SPEC`), sin escribir.
- `console`: captura una fase por HMP sobre el nodo indicado, delegando en
  `captures.capture_phase`; necesita nodo con monitor.
- `webui`: delega en `WebUICapture.from_env` y devuelve su resultado; si no está disponible,
  devuelve `reason` y `fallback="consola"`, sin lanzar excepción.
- `index`: delega en `captures.write_index` sobre las entradas pasadas o el índice existente.
- Carga de módulos con `importlib.util.spec_from_file_location` sobre la raíz del repo, con
  caché, como `_pfsense_module()`. Si un módulo falta, error claro con su nombre.
- Credenciales solo de entorno; `error` nunca incluye la contraseña.
- La tool **no configura nada**: solo lee y escribe ficheros de imagen/índice en `outdir`.

Tests propios `tests/test_mcp_capturas.py` con módulos falsos inyectados en `sys.modules`:
las cuatro acciones, degradación WebUI, error sin módulo y sin credenciales.

## Gates

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-capmcp
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile gns3_mcp_server.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q tests/test_mcp_capturas.py tests/test_mcp_optimization.py
python3 scripts/verify.py
```

Ojo: `tests/test_mcp_optimization.py` congela el conjunto de tools; añade `gns3_capturas` a
`TOOLS_CONTRATO` en ese fichero (única excepción permitida a «tests propios»).

Commit en `opencode/capmcp`; **no push a master**, no PR.
