# BRIEF — carril `fix-capturas` (swarm de fixes)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-fix-capturas` · rama `opencode/fix-capturas`.
Base: `master` en `50669b4`. Modelo asignado: **Hy4 Flash Free**.

## Alcance

Solo puedes modificar: captures.py, webui_capture.py y sus tests. No toques ningún otro archivo; otros carriles trabajan en paralelo.
Lee `AGENTS.md` antes de empezar. Los números vienen de `orchestration/INFORME-SWARM-2.md`.

## Hallazgos a arreglar (en orden)

1. MEDIA captures.py:35-42,52-63,88-107 — dos capturas concurrentes calculan el mismo número de fichero; reservar el nombre antes de guardar.
2. MEDIA webui_capture.py:180-196 — una página de error de navegación se cuenta como captura válida; comprobar respuesta/URL de cada navegación.

## Contrato

1. Cada hallazgo lleva su **test que falla sin el arreglo** y pasa con él. No quites tests existentes.
2. Mantén la cobertura del 100 % en `gns3core.py` y `pfsense.py` si tocas esos ficheros (gate del CI).
3. No añadas secretos ni credenciales literales; usa variables de entorno.
4. Verifica con los gates reales: suite completa (`env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q`), `python3 scripts/verify.py` y `python3 scripts/check-links.py`.
5. Si un hallazgo requiere tocar un archivo fuera de tu alcance, **no lo hagas**: reporta el bloqueo y sigue con los demás.

## Entrega

Commit en `opencode/fix-capturas`, `git push -u origin opencode/fix-capturas` y `gh pr create --base master`
(título con `fix:` y cuerpo enumerando los hallazgos numerados). No mergees. Reporta URL del PR,
tests ejecutados y cualquier hallazgo que no hayas podido arreglar.
