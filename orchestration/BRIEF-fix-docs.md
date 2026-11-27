# BRIEF — carril `fix-docs` (swarm de fixes)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-fix-docs` · rama `opencode/fix-docs`.
Base: `master` en `50669b4`. Modelo asignado: **Hy4 Flash Free**.

## Alcance

Solo puedes modificar: AGENTS.md, README.md, PROJECT.md y docs (NO tocar código ni scripts/labspec.py). No toques ningún otro archivo; otros carriles trabajan en paralelo.
Lee `AGENTS.md` antes de empezar. Los números vienen de `orchestration/INFORME-SWARM-2.md`.

## Hallazgos a arreglar (en orden)

1. MEDIA AGENTS.md:13,15 — dice 47 comandos y 700 tests; real 48 y 931. Actualizar y documentar 'python -m pytest -q' en vez de 'pytest -q' (issue #25). Ampliar scripts/verify.py para detectar la deriva de AGENTS.md.

## Contrato

1. Cada hallazgo lleva su **test que falla sin el arreglo** y pasa con él. No quites tests existentes.
2. Mantén la cobertura del 100 % en `gns3core.py` y `pfsense.py` si tocas esos ficheros (gate del CI).
3. No añadas secretos ni credenciales literales; usa variables de entorno.
4. Verifica con los gates reales: suite completa (`env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q`), `python3 scripts/verify.py` y `python3 scripts/check-links.py`.
5. Si un hallazgo requiere tocar un archivo fuera de tu alcance, **no lo hagas**: reporta el bloqueo y sigue con los demás.

## Entrega

Commit en `opencode/fix-docs`, `git push -u origin opencode/fix-docs` y `gh pr create --base master`
(título con `fix:` y cuerpo enumerando los hallazgos numerados). No mergees. Reporta URL del PR,
tests ejecutados y cualquier hallazgo que no hayas podido arreglar.
