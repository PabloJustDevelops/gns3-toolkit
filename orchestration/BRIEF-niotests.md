# BRIEF — carril `niotests` (cobertura 100 % con NIO y WS)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-niotests` · rama `opencode/niotests`.

## Contexto

`gns3core.py` tiene 12 áreas en `API_V2_MAP` y nuevos métodos: `port_nio`, `port_capture`,
`nodes_action`, `nodes_console_reset`, `node_action` con `resume|pause|unpause`,
`_emulator_for`, `qemu_img_binaries`, `qemu_img_config`, `virtualbox_vms`, `vmware_vms`,
`vmware_vmnet`, `notifications_ws_url`, `v1_version`. La suite actual tiene 416 tests al 100 %.

## Objetivo

**100 % de cobertura** con `--cov-fail-under=100`, sin servidor GNS3. Cubre cada método nuevo
en todos sus caminos:

- `port_nio` con `delete=True`, con body (PUT) y sin body (GET), con `emulator` explícito y
  inferido (`_emulator_for` con node_type y sin él).
- `port_capture` con las tres acciones y `ValueError` en una acción inválida; comprueba el
  body exacto de `start_capture` (`DLT_EN10MB` + nombre de fichero).
- `nodes_action` con las cuatro acciones válidas y `ValueError`; `nodes_console_reset`.
- `node_action` con `resume`, `pause`, `unpause` y rechazo de una acción inventada.
- `qemu_img_config` con y sin body, `virtualbox_vms`, `vmware_vms`, `vmware_vmnet`,
  `qemu_img_binaries`, `v1_version`.
- `notifications_ws_url` con y sin proyecto, con URL `http://` y `https://`.
- `API_V2_MAP` con 12 áreas y la presencia de `nio_ports`.

Usa los dobles de `tests/conftest.py`. Solo `# pragma: no cover` justificado en ramas
imposibles de simular.

## Prohibido

No edites `gns3core.py`, `gns3_mcp_server.py`, `cli/gns3lab`, `docs/` ni `PROJECT.md`.
Si un test destapa un bug, `xfail(strict=True, reason="BUG: ...")` y descríbelo; lo arregla
el padre. No `git push`, no PR, no cambio de rama.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-niotests
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q --cov=gns3core --cov-report=term-missing --cov-fail-under=100
```

Pega las últimas 15 líneas con porcentaje y total de tests.

Commit: `test: cobertura del 100 % con NIO, capturas por puerto y WS`. Informa de números y bugs.
