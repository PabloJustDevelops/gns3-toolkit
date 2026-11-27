# BRIEF — carril `hotfix-doble` (regresión por interacción de PRs #19 + #20)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-hotfixdoble` · rama `opencode/hotfixdoble`.
Base: `master` actual (`ce2b20e`), con los cuatro PRs ya mergeados.

## Error real (suite completa en master, `rc=1`)

```
FAILED tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense[None-telnet]
FAILED tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense[vnc-vnc]
FAILED tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense[spice-spice]
E   AttributeError: 'ClienteExamenFalso' object has no attribute 'json_list_or_die'
3 failed, 928 passed in 304.47s
```

## Causa

El PR #19 (issue #1) cambió `examen setup` para usar `Client.json_list_or_die(...)` en vez de
`Client.images(...)`. El doble `ClienteExamenFalso` de `tests/test_pf_console.py` (PR #20) solo
tiene los métodos viejos. Cada PR pasó su CI por separado; al mergear ambos, el doble ya no
satisface la interfaz.

## Contrato

1. Añadir `json_list_or_die` al doble `ClienteExamenFalso`, con la misma semántica que el real:
   devuelve la lista del path, lanza `RuntimeError(f"{what}: [{st}] {body}")` si el status no
   es 200 o el cuerpo no es lista.
2. Buscar **todos** los dobles de cliente en `tests/` que implementen `images()`/`links()` y
   que puedan servir a `examen setup`; añadir el método donde haga falta para que la clase de
   fallo no reaparezca en otra ruta. No cambiar código de producción.
3. Verificar que el propio test sigue comprobando lo que dice: que `examen setup` fija
   `console_type=telnet` por defecto y respeta `vnc`/`spice`.
4. Si faltase cobertura por el nuevo método en el doble, no hace falta cubrir el doble: la
   cobertura mide el código de producción.

## Gates

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-hotfixdoble
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q tests/test_pf_console.py tests/test_silent_errors.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q   # suite completa, ~5 min
python3 scripts/verify.py
```

## Entrega

Commit en `opencode/hotfixdoble`, `git push -u origin opencode/hotfixdoble` y
`gh pr create --base master` (los permisos ya están habilitados para ramas `opencode/*`).
No mergees. Reporta la URL del PR y el resultado de la suite completa.
