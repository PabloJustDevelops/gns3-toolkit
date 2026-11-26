# BRIEF — carril `capcore` (capturas por fase sobre HMP)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-capcore` · rama `opencode/capcore`.

## Contexto

El profesor pedirá capturas de cómo se monta el laboratorio, por fases, no 300 imágenes. Lee
`AGENTS.md`, `gns3core.py` (`QemuMonitor.screendump`, `ocr`, `screen_text`),
`scripts/labspec.py`, `docs/LAB-SPEC.md` y `examples/lab-ejemplo.yaml`.

**VNC es el último recurso**: la captura sale del monitor HMP, nunca de VNC. Pillow ya está
disponible en el venv y convierte el PPM; `tesseract` ausente degrada OCR a cadena vacía.

## Contrato

Fichero nuevo `captures.py` en la raíz, sin dependencias de terceros salvo Pillow opcional:

```python
def capture_phase(monitor, phase: str, outdir: str, node: str | None = None) -> dict
    # monitor: QemuMonitor ya conectado; screendump a fichero temporal PPM,
    # Pillow -> PNG en <outdir>/<NN>-<phase>.png, OCR x2 psm 4.
    # Devuelve {"ok", "phase", "path", "ocr", "node", "error"}.
    # Nunca lanza VNC ni instala nada. Si Pillow o tesseract faltan, degrada y lo reporta.

def write_index(entries: list[dict], outdir: str) -> str
    # escribe <outdir>/indice.md con tabla: fase | archivo | nodo | OCR (recortado)
    # y una línea de estado. Sin generar un informe largo: es solo el índice.

def phases_from_spec(spec: dict) -> list[dict]
    # lee spec["captures"] (opcional); máximo 5 fases; cada entrada
    # {"phase": "topologia", "after": "apply"|"verify", "node": "PF1"|None}.
    # Fase sin nombre o after desconocido -> error con la ruta del campo.
```

En `scripts/labspec.py` añadir parámetro opcional `captures=False` a `aplicar_deseado` y
`verificar` (default `False`, backwards compatible). Si `captures=True` y el spec declara
fases, invoca `captures.capture_phase` tras la fase correspondiente; un fallo de captura
**no** rompe el montaje: se reporta en el resultado y sigue.

## Tests

`tests/test_captures.py` (fichero propio): dobles de `QemuMonitor.screendump` que escriben un
PPM mínimo real, OCR falso, índice con 3 fases, degradación sin Pillow, límite de 5 fases y
que un fallo de captura no cambia el exit code de `aplicar_deseado`.

## Gates

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-capcore
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile captures.py scripts/labspec.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q tests/test_captures.py tests/test_labspec_diff.py
python3 scripts/verify.py
```

Commit en `opencode/capcore`; **no push a master**, no PR (los abriré yo tras verificar).
