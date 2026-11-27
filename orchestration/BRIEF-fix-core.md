# BRIEF — carril `fix-core` (swarm de fixes)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-fix-core` · rama `opencode/fix-core`.
Base: `master` en `50669b4`. Modelo asignado: **HungerG Free**.

## Alcance

Solo puedes modificar: gns3core.py y tests del núcleo. No toques ningún otro archivo; otros carriles trabajan en paralelo.
Lee `AGENTS.md` antes de empezar. Los números vienen de `orchestration/INFORME-SWARM-2.md`.

## Hallazgos a arreglar (en orden)

1. ALTA gns3core.py:927-936,998-999,1023-1047 — Console da ok=True al cerrar o por quietud aunque no se cumpliera expect; el bucle solo se detiene por timeout. Distinguir ' cerró', 'expect no cumplido' y 'timeout'.
2. MEDIA gns3core.py:168,550-554,582-584,835-851 — nombres de archivo interpolados en URL sin codificar; usar quote() preservando '/'.
3. MEDIA gns3core.py:1552-1569 — verify vpcs rechaza gateway por último octeto sin mirar el prefijo; usar ipaddress con la máscara.
4. MEDIA gns3core.py:914-919,942-955,985 — ConsoleError puede escapar durante envío desde wait_ready()/run_many(); envolverlo en la excepción pública de la clase.

## Contrato

1. Cada hallazgo lleva su **test que falla sin el arreglo** y pasa con él. No quites tests existentes.
2. Mantén la cobertura del 100 % en `gns3core.py` y `pfsense.py` si tocas esos ficheros (gate del CI).
3. No añadas secretos ni credenciales literales; usa variables de entorno.
4. Verifica con los gates reales: suite completa (`env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q`), `python3 scripts/verify.py` y `python3 scripts/check-links.py`.
5. Si un hallazgo requiere tocar un archivo fuera de tu alcance, **no lo hagas**: reporta el bloqueo y sigue con los demás.

## Entrega

Commit en `opencode/fix-core`, `git push -u origin opencode/fix-core` y `gh pr create --base master`
(título con `fix:` y cuerpo enumerando los hallazgos numerados). No mergees. Reporta URL del PR,
tests ejecutados y cualquier hallazgo que no hayas podido arreglar.
