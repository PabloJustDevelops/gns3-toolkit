# BRIEF — carril `fix-cli-examen` (swarm de fixes)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-fix-cli-examen` · rama `opencode/fix-cli-examen`.
Base: `master` en `50669b4`. Modelo asignado: **Seaglass Alpha Free**.

## Alcance

Solo puedes modificar: cli/gns3lab, tests de CLI de examen y docs/EXAMEN.md. No toques ningún otro archivo; otros carriles trabajan en paralelo.
Lee `AGENTS.md` antes de empezar. Los números vienen de `orchestration/INFORME-SWARM-2.md`.

## Hallazgos a arreglar (en orden)

1. ALTA cli/gns3lab:1179-1201 — _asegurar_wan() usa uuid sin import global (imports locales en 1301/1354/1442): NameError. Importar a nivel de módulo.
2. ALTA cli/gns3lab:3658-3668 — examen setup imprime 'listo' aunque fallen arranques; evaluar estados y devolver código de error.
3. ALTA cli/gns3lab:3555-3563,3593,3494-3495,3524-3528 — un fallo de precondición deja proyecto creado vacío y el reintento cree que ya está listo. Crear el proyecto solo tras validar, o limpiar/restaurar.
4. ALTA cli/gns3lab:3652-3656,3797-3805 — ignorar el HTTP de escritura del EXAMEN_MARKER hace que reset exija una marca inexistente.
5. MEDIA cli/gns3lab:4079-4086 — examen verify --json devuelve 2 sin JSON si el servidor está caído; enrutar esa ruta por el formateador.
6. MEDIA cli/gns3lab:1066-1087,1117-1135 — test considera exitosoVPCS sin consola o con error de conexión. Contar como fallo o.reportar no verificado.
7. MEDIA docs/EXAMEN.md:9,16-18,69-71 — tres nombres de proyecto: unificar a uno real y contrastar con cli/gns3lab.
8. MEDIA cli/gns3lab:3725-3777 — examen verify no comprueba enlaces prometidos ni mapa VLAN; añadir comprobación con dobles.

## Contrato

1. Cada hallazgo lleva su **test que falla sin el arreglo** y pasa con él. No quites tests existentes.
2. Mantén la cobertura del 100 % en `gns3core.py` y `pfsense.py` si tocas esos ficheros (gate del CI).
3. No añadas secretos ni credenciales literales; usa variables de entorno.
4. Verifica con los gates reales: suite completa (`env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q`), `python3 scripts/verify.py` y `python3 scripts/check-links.py`.
5. Si un hallazgo requiere tocar un archivo fuera de tu alcance, **no lo hagas**: reporta el bloqueo y sigue con los demás.

## Entrega

Commit en `opencode/fix-cli-examen`, `git push -u origin opencode/fix-cli-examen` y `gh pr create --base master`
(título con `fix:` y cuerpo enumerando los hallazgos numerados). No mergees. Reporta URL del PR,
tests ejecutados y cualquier hallazgo que no hayas podido arreglar.
