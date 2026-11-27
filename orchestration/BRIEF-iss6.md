# BRIEF — carril `iss6` (issue #6: símbolo por defecto al crear nodos por API)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-iss6` · rama `opencode/iss6`.

## Contexto

El issue #6: los nodos creados por API sin campo `symbol` salen con `computer.svg` en la GUI,
aunque su tipo tenga símbolo propio. Verificado en `examen-kit`: `NAT2`, `Cloud-lab` y `Cloud2`
como PCs, mientras `NAT1`/`PF1`, creados desde plantilla, muestran `nat.svg`/`firewall.svg`.
Lee `AGENTS.md`, `gns3core.py` (creación de nodos y `symbols()`), `cli/gns3lab` (`node add`) y
`gns3_mcp_server.py` (`gns3_nodes` action=add).

## Contrato

1. En el núcleo, un helper `default_symbol(node_type) -> str | None`: `cloud → cloud.svg`,
   `nat → nat.svg`; `qemu` devuelve `None` (no hay icono único correcto).
2. La creación de nodos por API acepta `symbol: str | None`. Si no se da y hay default, envía
   ese valor en el `POST /v2/projects/{id}/nodes`. Si no hay default, **no** inventa icono: lo
   deja como el servidor y lo reporta.
3. CLI `gns3lab node add` acepta `--symbol`; tool MCP `gns3_nodes(action="add")` acepta
   `symbol`. Si el servidor no tiene ese símbolo, error literal con los disponibles.
4. Tests con dobles: POST contiene `symbol` para cloud/nat, no lo contiene para qemu sin flag,
   y un símbolo inexistente produce error con la lista disponible.

## Gates

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-iss6
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q tests/test_node_symbols.py tests/test_cli_node.py tests/test_mcp_optimization.py
python3 scripts/verify.py
```

Si `tests/test_cli_node.py` no existe, usa el fichero de tests de CLI que corresponda y dilo.

## Entrega

Commit en `opencode/iss6`, push y `gh pr create ... --body "... Closes #6 ..."`, **sin mergear**.
Si el harness niega el push, dilo en una línea y espera: Hermes publica.
