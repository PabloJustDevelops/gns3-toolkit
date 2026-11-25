# BRIEF — carril `guitests` (cobertura 100 % del núcleo ampliado)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-guitests` · rama `opencode/guitests`.

## Contexto

`gns3core.py` creció con 40 métodos nuevos de la GUI operativa (`node_resize_disk`,
`console_reset`, `console_ws_url`, `node_links`, `node_idlepc`, `link_available_filters`,
`project_stats`, `project_duplicate`, `project_load`, `project_file_read/write`,
`compute_create/update/delete/ports/auto_idlepc/action`, `gns3vm*`, `notifications`,
`template_duplicate/base_configs/base_config`, `symbol_dimensions/raw/raw_upload/default_symbols`,
`iou_license*`, `server_shutdown/reload/debug`, `qemu_binaries/capabilities`, `docker_images`,
`network_interfaces/ports`, `udp_port`) y el mapa pasó a 11 áreas. La suite actual tiene 307 tests
y daba 100 % de cobertura sobre la versión anterior; ahora habrá ramas sin cubrir.

## Objetivo

Mantener **100 % de cobertura de `gns3core.py`** con `--cov-fail-under=100`, sin servidor
GNS3. Añade tests para cada método nuevo: éxito y error (status != 200, cuerpo inesperado),
y las ramas condicionales (por ejemplo `project_duplicate` con/sin `name`, `console_ws_url`
con `console_url`, sin `console_type` y con tipo no válido, `template_base_config` en lectura
y escritura, `compute_action` con y sin body).

Usa los dobles de `tests/conftest.py` y amplíalos si hace falta. Verifica que `API_V2_MAP`
tiene 11 áreas. Solo `# pragma: no cover` con justificación en ramas imposibles de simular.

## Prohibido

No edites `gns3core.py`, `gns3_mcp_server.py`, `cli/gns3lab`, `docs/` ni `PROJECT.md`.
Si un test destapa un bug, añádelo con `xfail(strict=True, reason="BUG: ...")` y descríbelo;
el arreglo lo hace el padre. No `git push`, no PR, no cambio de rama.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-guitests
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q --cov=gns3core --cov-report=term-missing --cov-fail-under=100
```

Pega las últimas 15 líneas con el porcentaje y el total de tests.

Commit: `test: cobertura del 100 % del núcleo con GUI portada`. Informa de tests totales,
cobertura y bugs documentados.
