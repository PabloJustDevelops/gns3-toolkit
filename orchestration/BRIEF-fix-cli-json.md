# BRIEF — carril `fix-cli-json` (swarm de fixes)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-fix-cli-json` · rama `opencode/fix-cli-json`.
Base: `master` en `50669b4`. Modelo asignado: **Hy4 Flash Free**.

## Alcance

Solo puedes modificar: cli/gns3lab y tests de CLI (NO tocar gns3core.py, scripts/labspec.py ni docs). No toques ningún otro archivo; otros carriles trabajan en paralelo.
Lee `AGENTS.md` antes de empezar. Los números vienen de `orchestration/INFORME-SWARM-2.md`.

## Hallazgos a arreglar (en orden)

1. MEDIA cli/gns3lab:4589-4595 + scripts/labspec.py:443-459 — lab apply --json mezcla progreso humano con JSON; capturar el progreso hacia stderr.
2. MEDIA cli/gns3lab:2722-2728 — cmd_all ignora --json local; formatear también esa ruta.
3. MEDIA cli/gns3lab:2906-2917 — watch --json escribe 'N evento(s)' en stdout; mandarlo a stderr o envolver la salida.
4. MEDIA cli/gns3lab:2758-2774 — vm vms --json emite un JSON por motor; acumular y emitir uno solo.
5. MEDIA cli/gns3lab:1857-1865,2261-2264,2425-2432,2514-2518 — borrados de snapshot/nodo/dibujo/enlace sin _confirm; aplicar confirmación homogénea.
6. MEDIA cli/gns3lab:1912-1933 — exec captura ConsoleError solo al obtener la consola; capturarlo también al enviar.
7. MEDIA cli/gns3lab:4634-4636,4403-4410 — lab en modo humano no muestra el error; pasarlo como texto.

## Contrato

1. Cada hallazgo lleva su **test que falla sin el arreglo** y pasa con él. No quites tests existentes.
2. Mantén la cobertura del 100 % en `gns3core.py` y `pfsense.py` si tocas esos ficheros (gate del CI).
3. No añadas secretos ni credenciales literales; usa variables de entorno.
4. Verifica con los gates reales: suite completa (`env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q`), `python3 scripts/verify.py` y `python3 scripts/check-links.py`.
5. Si un hallazgo requiere tocar un archivo fuera de tu alcance, **no lo hagas**: reporta el bloqueo y sigue con los demás.

## Entrega

Commit en `opencode/fix-cli-json`, `git push -u origin opencode/fix-cli-json` y `gh pr create --base master`
(título con `fix:` y cuerpo enumerando los hallazgos numerados). No mergees. Reporta URL del PR,
tests ejecutados y cualquier hallazgo que no hayas podido arreglar.
