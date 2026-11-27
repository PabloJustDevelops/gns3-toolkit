# Informe SWARM-swmcp

Carril `swmcp` (MCP en swarm). No existe brief propio (`orchestration/BRIEF-*swmcp*`,
`orchestration/SWARM-swmcp.md` no estaban presentes al empezar) ni skill de swarm activa;
alcance = revisar el estado real de este worktree y ejecutar los gates del repo
(`orchestration/GUIA-MANTENIMIENTO.md`). Este informe es la única modificación.

## Resumen

- **Carril MCP sin hallazgos**: `gns3_mcp_server.py` compila, `mcp.list_tools()` → **50 tools**,
  `scripts/verify.py` → `comandos=48 tools=50 áreas=12`, `OK: sin deriva`. Ninguna finding cae en
  `gns3_mcp_server.py`.
- **F1 (alta)**: suite `pytest -q` **no verde** en HEAD: `3 failed, 928 passed`, exit 1. 3 casos
  parametrizados de `tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense`
  fallan con `AttributeError`. Detalle y causa raíz en F1.
- **F2 (baja)**: deriva de cifras en `AGENTS.md` (`47 comandos`, real 48). `scripts/verify.py`
  no escanea `AGENTS.md`.
- **F3 (baja)**: deriva de cifras en `AGENTS.md` (`700 tests`, real 931 colectados). Misma causa
  raíz que F2. (La propia `GUIA-MANTENIMIENTO.md:119` dice `737 passed`, también desfasado, pero
  es una captura de sesión histórica.)
- `scripts/verify.py`, `scripts/check-links.py`, `py_compile`, `git diff --check`: **limpios**.

## Entorno

- Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-swmcp`
- Rama: `opencode/swmcp`
- HEAD: `ce2b20e fix(tests): quitar skipif obsoletos y añadir aserciones de contrato (#3) (#21)`
- `git status --short`: vacío al empezar; solo se añade este fichero al final.
- Python: `Python 3.12.14`, venv `.venv` (se invoca con `env -u PYTHONPATH -u VIRTUAL_ENV`).
- Entorno de red/servidor GNS3: no se usa; ningún gate de este informe necesita un servidor GNS3.
- Sin secretos: ninguna credencial leída, copiada ni escrita; `scripts/verify.py::_secretos` limpio.

## Gates ejecutados (comando · exit · salida literal)

1. `git status --short` · exit 0 · (sin salida; árbol limpio)
2. `git log -1 --oneline` · exit 0 · `ce2b20e fix(tests): quitar skipif obsoletos y añadir aserciones de contrato (#3) (#21)`
3. `.venv/bin/python -V` · exit 0 · `Python 3.12.14`
4. `env -u PYTHONPATH -u VIRTUAL_ENV python3 scripts/verify.py`
   · exit 0 ·
   ```text
   comandos=48 tools=50 áreas=12
   OK: sin deriva
   ```
5. `python3 scripts/check-links.py` · exit 0 · `OK: sin enlaces rotos`
6. `env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q`
   · **exit 1** ·
   ```text
   FAILED tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense[None-telnet]
   FAILED tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense[vnc-vnc]
   FAILED tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense[spice-spice]
   3 failed, 928 passed in 302.03s (0:05:02)
   ```
   (corrida previa idéntica: `3 failed, 928 passed in 301.10s (0:05:01)`; repro aislada abajo)
7. `git diff --check` · exit 0 · (sin salida)
8. `env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile gns3core.py pfsense.py gns3_mcp_server.py cli/gns3lab` · exit 0 · `compile_ok`
9. `mcp.list_tools()` sobre `gns3_mcp_server.py` · exit 0 · `tools: 50`
10. `bash -n scripts/install.sh skill-sync/scripts/gns3.sh` · no ejecutado en este informe (no se tocan esos ficheros).

## F1 (alta) — 3 tests fallan: `ClienteExamenFalso` sin `json_list_or_die`

### Síntoma (salida literal de la repro aislada)

Comando:

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-swmcp
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q \
  tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense
echo "pytest_exit=$?"
```

Salida (recorte literal, idéntico en las 3 variantes):

```text
FFF                                                                      [100%]
=================================== FAILURES ===================================
_____ test_examen_setup_fija_console_type_de_pfsense[None-telnet] _____

console_type = None, esperado = 'telnet'

    @pytest.mark.parametrize(("console_type", "esperado"), [(None, "telnet"), ("vnc", "vnc"), ("spice", "spice")])
    def test_examen_setup_fija_console_type_de_pfsense(console_type, esperado):
        cliente = ClienteExamenFalso()
        args = SimpleNamespace(from_project=None)
        if console_type is not None:
            args.console_type = console_type

>       rc = cli._examen_setup(args, {}, cliente, "Kit de examen")
E       AttributeError: 'ClienteExamenFalso' object has no attribute 'json_list_or_die'

tests/test_pf_console.py:325:
cli/gns3lab:3546: in _examen_setup
    disco, disponibles = _examen_disk(c, preferido, ocupados)
cli/gns3lab:3470: AttributeError
...
=========================== short test summary info ============================
FAILED tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense[None-telnet]
FAILED tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense[vnc-vnc]
FAILED tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense[spice-spice]
3 failed in 1.21s
pytest_exit=1
```

### Localización `fichero:línea`

- `cli/gns3lab:3463-3483` — `_examen_disk(c, preferred, en_uso)`.
- **`cli/gns3lab:3470`** — `imagenes = c.json_list_or_die("/v2/computes/local/qemu/images", "imágenes QEMU")`. Última modificación de esta línea: commit `fb0c10f` (`fix: no silenciar errores http en listados (#19)`).
- `cli/gns3lab:3546` — `_examen_setup(...)` llama `disco, disponibles = _examen_disk(c, preferido, ocupados)`.
- `gns3core.py:208-212` — `Client.json_list_or_die(path, what, **kw)`: `st, body = self.get(...)`; `if st != 200 or not isinstance(body, list): raise RuntimeError(...)`. **La API real sí tiene el método.**
- `tests/test_pf_console.py:321-330` — test `test_examen_setup_fija_console_type_de_pfsense`, parametrizado `[(None,"telnet"),("vnc","vnc"),("spice","spice")]`, construye `ClienteExamenFalso()` y llama `cli._examen_setup`; fallo en **`tests/test_pf_console.py:325`**.
- **`tests/test_pf_console.py:241-272`** — `ClienteExamenFalso`. Métodos: `projects`, `get`, `qemu_images`, `qemu_binaries`, … `qemu_images` en **`tests/test_pf_console.py:267-268`** devuelve `[{"filename": "pfSense.qcow2"}]`. **No implementa `json_list_or_die`.**
- `tests/test_pf_console.py` añadido en commit `f78806d` (`fix(pfsense): telnet por defecto y aviso de consolas gráficas (#20)`); HEAD `ce2b20e` no lo toca.

### Causa raíz

`cli/gns3lab:3470` exige `Client.json_list_or_die`, pero el doble de prueba `ClienteExamenFalso`
no lo implementa; solo expone la API antigua `qemu_images()`. Producción no está rota
(`gns3core.Client` sí tiene `json_list_or_die`, `gns3core.py:208`); **el doble del test quedó
obsoleto** respecto al endurecimiento de `fb0c10f`. La integración `fb0c10f` (#19) + `f78806d`
(#20) nunca tuvo suite verde con ambos. `scripts/verify.py` reporta `OK: sin deriva` porque **no
ejecuta tests** (`scripts/verify.py` `check()` solo contrasta cifras/enlaces/secretos). Incumple
`orchestration/GUIA-MANTENIMIENTO.md:37` (`pytest -q` termina en `N passed`, exit 0) y `:216`.
Además el mensaje del commit `ce2b20e` afirma `843 -> 852 tests en verde`, no reproducible:
recuento real **931** colectados (`928 passed + 3 failed`).

### Corrección sugerida (NO aplicada — tarea de solo informe)

Añadir al doble `ClienteExamenFalso` (`tests/test_pf_console.py:241`) un método, p.ej.:

```python
def json_list_or_die(self, path, what, **kw):
    if path == "/v2/computes/local/qemu/images":
        return [{"filename": "pfSense.qcow2"}]
    st, body = self.get(path, **kw)
    if st != 200 or not isinstance(body, list):
        raise RuntimeError(f"{what}: [{st}] {body}")
    return body
```

(sin tocar `cli/gns3lab` ni `gns3core.py`; el filtro `_examen_disk` exige `pfsense` + `.qcow2`,
`cli/gns3lab:3474`). No silenciar, no `skip`, no `xfail`. No verificado empíricamente aquí.

## F2 (baja) — `AGENTS.md:13` dice `47 comandos`, real 48

- **`AGENTS.md:13`**: `CLI de **47 comandos**` para `cli/gns3lab`.
- Real: `handlers` en `cli/gns3lab` tiene **48** claves; `scripts/verify.py` imprime `comandos=48`.
- Consistente con `README.md` (`48 subcomandos`) y `PROJECT.md` (`48 comandos`); `AGENTS.md` es el outlier.
- Causa raíz: `scripts/verify.py:17` `DOCUMENTOS = ("README.md","PROJECT.md","docs/GUI-PORTADA.md")`
  (+ `docs/**/*.md` + skill, `:181`); **`AGENTS.md` no se escanea**, y `CIFRA_RE` (`scripts/verify.py:24`)
  solo captura números antes de `áreas|area|areas|tools|comandos|subcomandos`. Por eso `OK: sin deriva`.

Repro:

```bash
python3 scripts/verify.py | head -1                 # comandos=48 tools=50 áreas=12
grep -n '47 comandos' AGENTS.md                     # AGENTS.md:13
grep -n '48' README.md PROJECT.md | grep -i 'comand\|subcomand' | head
```

## F3 (baja) — `AGENTS.md:16` dice `700 tests`, real 931

- **`AGENTS.md:16`**: `pytest: **700 tests**`. Recuento real **931** colectados (`928 passed + 3 failed`).
- Misma causa raíz que F2 (`AGENTS.md` no está en `scripts/verify.py::DOCUMENTOS`, y `CIFRA_RE`
  no incluye `tests`). Corregir la cifra no basta mientras F1 siga roja.
- `orchestration/GUIA-MANTENIMIENTO.md:119` muestra `737 passed in 271.00s` como "salida real de
  esta sesión" (histórico, no contrastado); `PROJECT.md` tiene `840 passed`/`852` en secciones
  marcadas `hito`/históricas, excluidas por `scripts/verify.py::HISTORIA_RE`.

Repro:

```bash
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q 2>&1 | tail -1
```

## Carril MCP (`swmcp`) — sin hallazgos

- `gns3_mcp_server.py` compila (`py_compile`, exit 0).
- `mcp.list_tools()` → **50** tools; `scripts/verify.py` `tools=50`; `AGENTS.md:11` dice 50.
- `scripts/verify.py` `OK: sin deriva`; `scripts/check-links.py` `OK: sin enlaces rotos`.
- `git diff --check` limpio; sin secretos (`_secretos`, `scripts/verify.py`).
- Ninguna finding de F1/F2/F3 reside en `gns3_mcp_server.py`; F1 es `cli/gns3lab` + `tests/`, no el servidor MCP.

## Reproducibilidad (script completo)

```bash
set -e
cd /home/pablorg/Proyectos/gns3-toolkit-wt-swmcp
git rev-parse --abbrev-ref HEAD                     # opencode/swmcp
git rev-parse --short HEAD                          # ce2b20e
git status --short                                  # vacío
.venv/bin/python -V                                 # Python 3.12.14

# gates que pasan (exit 0):
env -u PYTHONPATH -u VIRTUAL_ENV python3 scripts/verify.py        # comandos=48 tools=50 áreas=12 / OK: sin deriva
python3 scripts/check-links.py                                    # OK: sin enlaces rotos
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile \
  gns3core.py pfsense.py gns3_mcp_server.py cli/gns3lab
git diff --check

# gate que FALLA (exit 1): F1
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q    # 3 failed, 928 passed; exit 1
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q \
  tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense   # 3 failed; exit 1
```

## Lo que NO se verificó

- Gates que necesitan un servidor GNS3 2.2 real o el harness externo (`gns3lab doctor`,
  `hermes mcp test gns3`, `scripts/install.sh`, hooks de `wt merge`, gates sobre checkout
  canónico `gk7-integ`, `skill-sync` instalada en `~/.hermes/...`): **no ejecutados**; no se
  afirma nada sobre ellos. No se creó/borró proyecto, no se cambió estado de servidor.
- `bash -n scripts/install.sh` / `bash -n skill-sync/scripts/gns3.sh`: no ejecutados (ficheros no tocados).
- Corrección de F1/F2/F3 **no aplicada**: la tarea es únicamente producir este informe. F1 no
  validado tras el parche sugerido.
- No hay brief `SWARM-swmcp` original que defina otras entregas del carril; se informa del estado
  real verificado. Si el carril `swmcp` tenía otra tarea pendiente, no está en este worktree.

## Cambios realizados

- Único cambio: creación de `orchestration/SWARM-swmcp.md` (este fichero). Sin push, sin PR, sin
  tocar `gns3_mcp_server.py`, `gns3core.py`, `cli/gns3lab`, `tests/`, `scripts/`, docs de producto
  ni `AGENTS.md`. Sin silenciar ningún gate.
