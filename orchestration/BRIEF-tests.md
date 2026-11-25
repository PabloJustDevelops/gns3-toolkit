# BRIEF — carril `tests`

Eres un agente de coding. Trabajas SOLO en este worktree:

- Ruta: `/home/pablorg/Proyectos/gns3-toolkit-wt-tests`
- Rama: `opencode/tests` (ya creada, no cambies de rama)
- Repo base: `/home/pablorg/Proyectos/gns3-toolkit`

## Contexto que no se infiere del código

`gns3core.py` es el núcleo compartido por un servidor MCP y una CLI. Trabaja contra un
servidor **GNS3 2.2** (`http://127.0.0.1:3080`, API `/v2`), pero **tus tests no pueden
necesitar ese servidor ni el GNS3 instalado**: usan dobles locales.

Lee antes de escribir: `AGENTS.md`, `PROJECT.md`, `gns3core.py`, `gns3_mcp_server.py` y
`cli/gns3lab` (lee, no edites los tres últimos).

## Qué tienes que entregar

Suite `pytest` en `tests/`, sin red externa ni servidor GNS3, que cubra:

1. **`key_for` y `text_to_sendkey`**: `a`→`a`, `A`→`shift-a`, `0`→`0`, `-`→`minus`,
   `.`→`dot`, ` `→`spc`, `\n`→`ret`, `@`→`shift-2`, `>`→`shift-dot`, `:`→`shift-semicolon`,
   `_`→`shift-minus`, `?`→`shift-slash`. Un carácter no mapeable devuelve `None`.
2. **`Client`** contra un `http.server` en un hilo: `alive()`, `projects()`, `nodes()`,
   `resolve_project` por nombre parcial, por id, y **error cuando hay dos abiertos**;
   `match_nodes` con `*`, `R*`, `[12]`, lista con comas.
3. **`Console`** contra un servidor telnet falso (`socketserver.ThreadingTCPServer`):
   - detecta el prompt y `wait_ready` devuelve `ready=True`;
   - `run("show ip")` devuelve la salida **sin el eco del comando**;
   - **paginación**: el falso responde `--More--` y el cliente manda espacio y sigue;
   - **confirmación**: manda `[y/n]` y el cliente responde `y` sin colgarse;
   - **timeout**: si el falso no devuelve nada, `timed_out=True` y `ok=False` en un tiempo acotado.
4. **`QemuMonitor.run`** contra un HMP falso: el falso imita el eco carácter a carácter con
   `\x1b[K` y `\x1b[D` antes de la respuesta; comprueba que `run("info status")` devuelve
   `VM status: running` **sin** el eco, y que `error` se rellena con `Error: ...`.
5. **`node_file_write`**: verifica con un capturador que el `Content-Type` es `text/plain` y
   que el cuerpo va **crudo** (no `{"content": ...}`).
6. **`clean`**: quita ANSI y `\ufffd` de la negociación telnet.

Además, un `tests/conftest.py` con las fixtures de los dobles y un `pytest.ini` o
`pyproject.toml` con `testpaths = ["tests"]`.

## Prohibido

- **No edites** `gns3core.py`, `gns3_mcp_server.py` ni `cli/gns3lab`. Si un test destapa un
  bug real en ellos, **no lo arregles**: añade el test marcado `@pytest.mark.xfail(strict=True,
  reason="BUG: <descripción>")` y descríbelo en el informe final.
- No toques `README.md`, `docs/` ni `PROJECT.md` (los lleva otro carril).
- No `git push`, no PR, no deploy. No cambies de rama. No toques otros worktrees.

## Gates (pega la salida real)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-tests
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile gns3core.py gns3_mcp_server.py cli/gns3lab
```

El `.venv` ya existe en el worktree (post-start copió los ignorados) y tiene `pytest`.
Si no hubiera venv: `uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python fastmcp httpx pillow pytest`.

## Entrega

Commit en tu rama, mensaje `test: suite de gns3core sin servidor GNS3`, y en el informe:
número de tests, salida literal de `pytest -q`, bugs encontrados (con el xfail) y cualquier
sitio donde el código no se deje probar sin red.
