# BRIEF — carril `findmon` (PR del issue #4)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-findmon` · rama `opencode/findmon`.

## Contexto

El issue #4 del repo describe un bug en `find_monitor_port()`: si el llamador pasa `node_id`,
el filtro por nombre de disco puede descartar el proceso correcto porque el disco copiado al
proyecto se llama distinto. Hay un parche ya escrito por otro agente en
`/tmp/issue4.patch` (cambio de una condición en `gns3core.py` más un test en `tests/test_proc.py`).
Verificado en limpio: `pytest -q tests/test_proc.py` → 9 passed. **No lo reescribas desde cero**.

## Qué hacer

1. Aplica el parche: `git apply /tmp/issue4.patch` desde la raíz del worktree.
2. Demuestra ROJO→VERDE: con el test aplicado pero sin el cambio de `gns3core.py`, el test
   nuevo debe fallar; con el cambio, pasa. Guarda ambas salidas literales.
3. Verifica: `pytest -q tests/test_proc.py`, suite completa, `scripts/verify.py`,
   `scripts/check-links.py`.
4. Commit en `opencode/findmon`, `git push -u origin opencode/findmon` y
   `gh pr create --base master --head opencode/findmon --title "fix(core): find_monitor_port prioriza node_id sobre el nombre de disco"`,
   citando el issue #4 y las salidas rojo/verde. **No mergear el PR ni tocar master.**

Si el harness te niega `git push`, recognoslo con una sola línea y espera: Hermes publica la
rama por ti. No reintenteces a ciegas.

## Prohibido

No toques `cli/gns3lab`, `gns3_mcp_server.py`, `captures.py`, `webui_capture.py` ni docs.
