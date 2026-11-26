# BRIEF — carril `mcptpl` (propagar errores HTTP de plantillas en el MCP)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-mcptpl` · rama `opencode/mcptpl`.

## Contexto

El issue #1 del repo documenta la clase de bug: `gns3core.Client` convierte errores HTTP en
listas vacías y los call sites lo leen como «no hay nada». El PR #2 ya arregló la CLI y está
mergeado en `master` (commit `3d4a6f0`); **no toques la CLI**. Lee `AGENTS.md`,
`gns3_mcp_server.py` y los tests MCP existentes.

Quedan tres call sites en el MCP que仍需 arreglo:

1. `_resolve_template` (≈343): `client.templates()` → si HTTP 500 devuelve «el servidor no tiene
   plantillas».
2. `gns3_node_edit`, rama `action == "create"` (≈2423): dos lecturas `client.templates()` →
   «plantilla no encontrada» con `available: []`.
3. `gns3_template`, rama `action == "add"` (≈1336): `_api("GET", "/v2/templates") or []` → un
   error se convierte en lista vacía.

## Contrato

- Añade un helper `_mcp_templates(client)` que use `client.json_or_die("/v2/templates",
  "plantillas")`, compruebe que el cuerpo es lista y lance `RuntimeError` si no. Úsalo en 1 y 2.
- En 3, usa el helper de API del fichero para detectar error antes de convertir a lista: si
  `_api` devuelve un dict con `error`/`detail` o un status distinto de 200, propaga ese error
  en el resultado de la tool; nunca lo sustituyas por `[]`.
- No cambies `gns3core.py` ni el comportamiento por defecto de `Client`. No toques `cli/gns3lab`.
- Tests nuevos en `tests/test_mcp_template_errors.py` con dobles que devuelven HTTP 500:
  el error debe contener `[500]` y no «no tiene plantillas» / «plantilla no encontrada».
  Añade una comprobación de que no quedan lecturas directas en esos tres puntos.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-mcptpl
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile gns3_mcp_server.py tests/test_mcp_template_errors.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q tests/test_mcp_template_errors.py tests/test_mcp_optimization.py
python3 scripts/verify.py
python3 scripts/check-links.py | tail -2
```

## Flujo obligatorio de entrega (PR, NO push a master)

1. Commit en la rama `opencode/mcptpl`.
2. `git push -u origin opencode/mcptpl`.
3. `gh pr create --base master --head opencode/mcptpl --title ... --body ...` citando el issue #1
   y el PR #2 como trabajo previo. **No mergear el PR.** No tocar `master`.
4. Reporta la URL del PR y la salida literal de los gates.

Si encuentras otro call site de la misma clase, añádelo al mismo PR con su test.
