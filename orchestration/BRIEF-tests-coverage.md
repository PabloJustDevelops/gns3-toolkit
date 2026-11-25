# BRIEF — carril `tests` (cobertura del 100% del núcleo)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-tests` · rama `opencode/tests` (no cambies).

## Contexto

Los 54 tests actuales dan **60 % de cobertura sobre `gns3core.py`** (medido con
`pytest --cov=gns3core --cov-report=term-missing`): 204 sentencias sin ejecutar.
`gns3core.py` acaba de crecer con la superficie v2 completa (`computes`, `compute`,
`statistics`, `symbols`, `appliances`, `images`, `project_get/close/delete`,
`template_get/update/delete`, `node_action`, `node_command_line`, `link_update/delete/capture`,
`drawing_update/delete`, `snapshots/snapshot_create/restore/delete`, `drawings/drawing_create`,
`compute_write_file`, `API_V2_MAP`).

## Objetivo

**100 % de cobertura de `gns3core.py`**, sin servidor GNS3: amplía los dobles de
`tests/conftest.py` (HTTP server en hilo, telnet falso, HMP falso) y añade los tests que
faltan. Usa `pytest-cov` (ya instalado en el venv).

Cubre, como mínimo:

- Todos los métodos nuevos de `Client`, incluidos los caminos de error (status distinto de
  200, cuerpo no lista/dict) y los `ValueError` de `node_action`/`link_capture`.
- `link_capture` con sus tres acciones y el body exacto de `start_capture`.
- `node_file_read` / `node_file_write` (ctype `text/plain`, cuerpo crudo).
- `Console.wait_ready` con GRUB y sin prompt; `run` con `--More--`, `[y/n]`, `Password:`,
  timeout y `expect`; `run_many`; `wake`; `close` y escritura sobre socket roto.
- `QemuMonitor`: `run` con error HMP, `sendkey`, `type_text` con `wake`, `screendump`
  (con Pillow y sin él, con `magick` y sin ninguno), `find_monitor_port` sobre un `/proc`
  simulado, `key_for` de todo el mapa.
- `Client.resolve_project` en sus nueve ramas (vacío, por nombre, por id, ambiguo, varios
  abiertos con `matcher`, ninguno abierto, uno solo).
- `API_V2_MAP`: comprueba que las 8 áreas están presentes.

Solo se permite `# pragma: no cover` en ramas imposibles de simular (p. ej. un error de
sistema operativo), con un comentario que diga por qué.

## Prohibido

- **No edites** `gns3core.py`, `gns3_mcp_server.py`, `cli/gns3lab`, `docs/`, `README.md` ni
  `PROJECT.md`. Si un test destapa un bug, añádelo con `xfail(strict=True, reason="BUG: …")`
  y descríbelo en el informe; el arreglo lo hace el padre tras el merge.
- No `git push`, no PR, no cambio de rama.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-tests
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q --cov=gns3core --cov-report=term-missing --cov-fail-under=100
```

Pega las últimas 15 líneas con el informe de cobertura y el total de tests.

Commit en tu rama con mensaje `test: cobertura del 100% de gns3core`. Informa del porcentaje,
del número de tests y de los bugs que hayas documentado con xfail.
