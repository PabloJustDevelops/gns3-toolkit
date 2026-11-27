# BRIEF — carril `fix-mcp` (swarm de fixes)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-fix-mcp` · rama `opencode/fix-mcp`.
Base: `master` en `50669b4`. Modelo asignado: **Seaglass Alpha Free**.

## Alcance

Solo puedes modificar: gns3_mcp_server.py y tests de MCP. No toques ningún otro archivo; otros carriles trabajan en paralelo.
Lee `AGENTS.md` antes de empezar. Los números vienen de `orchestration/INFORME-SWARM-2.md`.

## Hallazgos a arreglar (en orden)

1. ALTA gns3_mcp_server.py:3784-3805 — gns3_batch solo bloquea algunas operaciones destructivas; cubrir todas las mutaciones equivalentes sin confirm.
2. ALTA gns3_mcp_server.py:569-586,4000-4009 — redacta usuario antes que contraseña y deja sufijos; ordenar por secretos más largos primero y no dejar residuos.
3. ALTA gns3_mcp_server.py:3044-3056 — export para nodos antes del try/finally y rearranca en un bucle sin aislar; verificar estados HTTP y garantizar rearranque por nodo.
4. MEDIA gns3_mcp_server.py:2110-2133 — fallback PCAP etiqueta la captura más reciente como si fuera el enlace pedido; no atribuir un PCAP ajeno.
5. MEDIA gns3_mcp_server.py:3033-3036,2445-2453,3080-3090 — importar exige proyecto previo aunque la rama crea uno nuevo; reordenar resolución.
6. MEDIA gns3_mcp_server.py:110-143,3960-3966 — cliente HTTP compartido y cerrado sin sincronizar; no cerrar el prestado.

## Contrato

1. Cada hallazgo lleva su **test que falla sin el arreglo** y pasa con él. No quites tests existentes.
2. Mantén la cobertura del 100 % en `gns3core.py` y `pfsense.py` si tocas esos ficheros (gate del CI).
3. No añadas secretos ni credenciales literales; usa variables de entorno.
4. Verifica con los gates reales: suite completa (`env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q`), `python3 scripts/verify.py` y `python3 scripts/check-links.py`.
5. Si un hallazgo requiere tocar un archivo fuera de tu alcance, **no lo hagas**: reporta el bloqueo y sigue con los demás.

## Entrega

Commit en `opencode/fix-mcp`, `git push -u origin opencode/fix-mcp` y `gh pr create --base master`
(título con `fix:` y cuerpo enumerando los hallazgos numerados). No mergees. Reporta URL del PR,
tests ejecutados y cualquier hallazgo que no hayas podido arreglar.
