# BRIEF — carril `driftguard` (guard automático de deriva docs/código)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-driftguard` · rama `opencode/driftguard`.

## Contexto

En las últimas tandas hubo que corregir a mano cifras obsoletas en README, PROJECT.md,
`docs/GUI-PORTADA.md` y la skill: decían 34 tools / 37 comandos cuando el código ya tenía
otros números, y quedaron 98 marcas «en curso» sin revisar. Hay que automatizar esa comprobación.

Lee `AGENTS.md`, `PROJECT.md`, `README.md`, `docs/GUI-PORTADA.md`, `scripts/install.sh`,
`gns3core.py`, `cli/gns3lab`, `gns3_mcp_server.py` y la skill real
`~/.hermes/skills/devops/gns3-lab-automation/SKILL.md` (solo lectura).

## Contrato

1. **`scripts/verify.py`** (stdlib, ejecutable, sin servidor) que compruebe:
   - Cuenta real de comandos (`handlers` en `cli/gns3lab`), tools (`@mcp.tool` en
     `gns3_mcp_server.py`) y áreas (`API_V2_MAP` en `gns3core.py`). Extrae los números del
     código, no de constantes escritas a mano.
   - Cualquier cifra declarada en `README.md`, `PROJECT.md`, `docs/*.md` y la skill que
     contradiga esos conteos se reporta con fichero:línea.
   - Marcas «en curso» en `docs/GUI-PORTADA.md` que correspondan a símbolos ya existentes en
     el código (se buscan por nombre de comando/tool).
   - Enlaces relativos rotos en `docs/` y `skill-sync/`.
   - Secretos en ficheros versionados (mismo patrón usado antes: `password|api_key|token|secret`
     seguido de un literal).
   Salida: lista de hallazgos y `OK`/`DRIFT`. Exit code 0 sin hallazgos, 1 con deriva, 2 si no
   puede leer un fichero obligatorio. Debe ser **solo lectura**: no modifica nada.
2. **`tests/test_drift.py`** que ejecute `verify.py` contra el repo y exija exit code 0,
   más un caso sintético (directorio temporal con un README que declare un número falso) que
   exija exit code 1. Sin servidor GNS3.
3. Añade `scripts/verify.py` al flujo de `scripts/install.sh` como paso opcional (una línea,
   sin cambiar su comportamiento).

## Prohibido

No edites `gns3core.py`, `gns3_mcp_server.py`, `cli/gns3lab`, `tests/test_batch.py` (lo lleva
otro carril), `docs/`, `README.md`, `PROJECT.md` ni la skill real. No `git push`, no PR, no
cambio de rama. Si el guard encuentra deriva **real** en el repo actual, no la corrijas tú:
repórtala con fichero:línea para que el padre la arregle tras el merge.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-driftguard
python3 scripts/verify.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q tests/test_drift.py
```

Commit: `test: guard automático de deriva entre docs, skill y código`. Informa de salida real y
de cualquier deriva encontrada.
