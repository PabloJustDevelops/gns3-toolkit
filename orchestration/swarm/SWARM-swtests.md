# Informe SWARM — swtests

- **Repo**: `/home/pablorg/Proyectos/gns3-toolkit-wt-swtests`
- **Rama**: `opencode/swtests`
- **Commit base**: `ce2b20eda644acc6e19030f5f62c92d9be6e2d92`
- **Alcance**: verificación ejecutable del worktree; no se han modificado `gns3core.py`, `cli/gns3lab`, `pfsense.py`, `gns3_mcp_server.py` ni tests. Sólo se escribe este informe.
- **Resultado**: hay **1 hallazgo** con 3 fallos de test; no se demuestra un bug adicional de producción.

## Hallazgos

### 1. `test_examen_setup_fija_console_type_de_pfsense` falla porque el doble `ClienteExamenFalso` no implementa `json_list_or_die`

**Tipo**: suite roja / doble de test incompleto. **No se demuestra bug de producción**: `gns3core.Client` sí define el método que usa `cli/gns3lab`.

**Cadena de llamada**:

- `cli/gns3lab:3519` `_examen_setup(...)`.
- `cli/gns3lab:3546` llama `_examen_disk(c, preferido, ocupados)`.
- `cli/gns3lab:3463` `_examen_disk(...)`.
- `cli/gns3lab:3470` ejecuta `imagenes = c.json_list_or_die("/v2/computes/local/qemu/images", "imágenes QEMU")`.
- `tests/test_pf_console.py:319` `test_examen_setup_fija_console_type_de_pfsense(...)`.
- `tests/test_pf_console.py:320-325` construye `ClienteExamenFalso()` y llama `cli._examen_setup(args, {}, cliente, "Kit de examen")`.
- `tests/test_pf_console.py:241` `class ClienteExamenFalso`.
- `tests/test_pf_console.py:253-265` `get()` no reconoce `/v2/computes/local/qemu/images` y devolvería `(404, {"message": ...})`, pero no se llega a `get`.
- `tests/test_pf_console.py:267-268` define `qemu_images()` devolviendo `[{"filename": "pfSense.qcow2"}]`, pero `cli/gns3lab:3470` no usa `qemu_images()`.
- `tests/test_pf_console.py:241-316` no define `json_list_or_die`.
- `gns3core.py:208-213` `Client.json_list_or_die` sí existe y exige `st == 200` y `isinstance(body, list)`, lanzando `RuntimeError` si no.

**Fallos observados** (3 parametrizaciones de la misma prueba):

```text
FAILED tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense[None-telnet]
FAILED tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense[vnc-vnc]
FAILED tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense[spice-spice]
```

**Error literal**:

```text
cli/gns3lab:3470: AttributeError
E       AttributeError: 'ClienteExamenFalso' object has no attribute 'json_list_or_die'
```

**Corrección sugerida, no aplicada**: actualizar el doble de test (`tests/test_pf_console.py:241`, p. ej. `ClienteExamenFalso`) para implementar `json_list_or_die(path, what, **kw)` con semántica equivalente a `gns3core.Client.json_list_or_die`, y devolver imágenes QEMU para `GET /v2/computes/local/qemu/images`, incluyendo `pfSense.qcow2`. No se ha tocado test ni producción porque este informe sólo registra hallazgos.

## Reproducibilidad

Mínima, sólo los 3 fallos:

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-swtests
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q \
  'tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense'
```

Salida observada en esta sesión:

```text
FFF                                                                      [100%]
...
3 failed in 1.28s

Exit code: 1
```

Completa, mismo resultado dentro de la suite:

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-swtests
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q
```

Salida observada:

```text
3 failed, 928 passed in 303.46s (0:05:03)

Exit code: 1
```

Los 3 `FAILED` son los listados arriba.

## Gates ejecutados

1. `env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q`
   → **exit 1** → `3 failed, 928 passed in 303.46s (0:05:03)`.
2. `env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q 'tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense'`
   → **exit 1** → `3 failed in 1.28s`.
3. `env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile gns3core.py gns3_mcp_server.py cli/gns3lab`
   → **exit 0** → sin salida.
4. `env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python scripts/verify.py`
   → **exit 0** → `comandos=48 tools=50 áreas=12` + `OK: sin deriva`.

## Ficheros tocados

- `orchestration/SWARM-swtests.md` — este informe.

**Commit**: no se ha hecho commit. **Push**: no. **Bloqueos**: la suite no está verde por los 3 fallos anteriores; `py_compile` y `verify.py` sí pasan.
