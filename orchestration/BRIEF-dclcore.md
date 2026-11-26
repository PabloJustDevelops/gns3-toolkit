# BRIEF — carril `dclcore` (export y diff declarativo sobre labspec)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-dclcore` · rama `opencode/dclcore`.

## Contexto

Ya existe `scripts/labspec.py` (407 líneas) con `leer/validar/normalizar/ordenes/ejecutar/
capturar/aplicar/verificar` y subcomandos `validate|plan|apply|verify`. **`docs/LAB-SPEC.md`**
documenta el esquema v1 (`project`, `nodes[name,template,adapter_type,ip]`, `links[a,b,pa,pb]`,
`expect`). Lee esos tres ficheros y `AGENTS.md` antes de tocar nada.

El salto que falta: **exportar** una topología real a spec y **comparar** deseado vs real para
que `apply` sea idempotente. Construye sobre `labspec.py`, no lo reescribas y no dupliques la API.

## Contrato (los otros carriles programan contra esto)

En `scripts/labspec.py`, añadir sin romper las firmas ni el comportamiento actual:

```python
def export(topology: dict, project: str | None = None) -> dict
    # topology: {"project": str, "nodes": [{"name","template"|"node_type",
    #            "properties":{"adapter_type": ...}}],
    #            "links": [{"ends":[{"node","adapter"},{"node","adapter"}]}]}
    # devuelve un spec v1 normalizado y válido. Nunca inventa ip ni expect.
    # template se toma de node_type o template; adapter_type de properties.
    # links se convierten a {a,b,pa,pb}. Si un enlace no tiene dos extremos,
    # se omite y se reporta en `warn` (no se lanza excepción).

def diff(deseado: dict, actual: dict) -> dict
    # ambos normalizados. Devuelve:
    # {"crear_nodos": [{name,template,adapter_type}], "crear_enlaces": [{a,b,pa,pb}],
    #  "sobrantes_nodos": [str], "sobrantes_enlaces": [{"a","b","pa","pb"}],
    #  "sin_cambios": bool}
    # Compara por nombre de nodo y por (a,pa,b,pb) normalizado (orden estable).
    # `sobrantes` se informan, NUNCA se borran.

def plan(deseado: dict, actual: dict, server: str | None = None) -> list[list[str]]
    # órdenes gns3lab para crear sólo lo que falta; omite `new` si actual.project existe.
    # mismos subcomandos que `ordenes`: node add / node props / link add / up.

def aplicar_deseado(deseado, actual, server, yes) -> int
    # usa plan(deseado, actual); sin yes imprime y devuelve 2 sin escribir;
    # con yes ejecuta en orden y para en el primer fallo. No borra nada.
```

`main()` añade los subcomandos `export` (lee `--topology <fichero.json>` con la topología ya
obtenida; también acepta `--stdin`) y `diff` (recibe `--spec` y `--topology`, imprime JSON).
`aplicar` existente queda como wrapper de `aplicar_deseado` con `actual={}` para no romper
scripts antiguos. `--json` global opcional para `diff`.

## Prohibido

No edites `gns3core.py`, `gns3_mcp_server.py`, `cli/gns3lab`, `tests/`, `docs/`, `README.md`
ni `PROJECT.md`. No `git push`, no PR, no cambio de rama. No escribas en un servidor GNS3:
todo se prueba con topologías de ejemplo en disco.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-dclcore
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile scripts/labspec.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python - <<'EOF'
import sys; sys.path.insert(0,"scripts")
import labspec as L
topo={"project":"p","nodes":[{"name":"pc1","node_type":"vpcs","properties":{"adapter_type":"e1000"}}],
      "links":[{"ends":[{"node":"pc1","adapter":0},{"node":"sw1","adapter":0}]}]}
e=L.export(topo); print("export:", L.validar(e), e["nodes"], e["links"])
d=L.diff(e, {"project":"p","nodes":[],"links":[]})
print("diff:", d["crear_nodos"], len(d["crear_enlaces"]), d["sin_cambios"])
print("idempotente:", L.diff(e,e)["sin_cambios"], L.plan(e,e))
EOF
```

Commit: `feat(spec): exportar topología y diff idempotente`. Informa de salida real.
