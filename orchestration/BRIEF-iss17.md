# BRIEF — carril `iss17` (issue #17: consola serie por defecto en pfSense)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-iss17` · rama `opencode/iss17`.

## Contexto

El issue #17: las plantillas/nodos QEMU de pfSense vienen con `console_type=vnc`, lo que obliga
a `shot` + OCR en vez de `exec`. Evidencia: nodo de `Practica VPN` con `vnc:5904`. Lee
`AGENTS.md`, `gns3core.py` (`verify_component`, nodos), `cli/gns3lab` (`verify`, `doctor`,
`node props`), `docs/PFSENSE-NATIVO.md` y `docs/VERIFICACION.md`.

## Contrato (alcance del issue)

1. `gns3lab verify` y `doctor` (y su tool MCP equivalente) avisan cuando un nodo qemu con
   consola `vnc`/`spice` podría usar `telnet`. El aviso incluye el comando exacto:
   `gns3lab node props <nombre> --set console_type=telnet -p <proyecto>` y la nota «con el nodo
   parado». No cambies nodos existentes automáticamente.
2. Si el toolkit crea plantillas o nodos pfSense por API, fija `console_type=telnet` por defecto
   con un flag explícito para `vnc`/`spice`. Si no hay tal creación en el código, no la inventes:
   limitate al aviso y documenta el comando de cambio.
3. `docs/PFSENSE-NATIVO.md`: cuándo hace falta VNC (solo instalación inicial del ISO) y cuándo
   basta telnet (todo el flujo nativo `assign/ip/dhcp/rule/nat/ssh`).
4. Tests con dobles: nodo vnc → aviso con el comando; nodo telnet → sin aviso; qemu no-pfSense
   → sin aviso.

## Gates

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-iss17
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q tests/test_pf_console.py tests/test_cli_doctor.py
python3 scripts/verify.py
python3 scripts/check-links.py | tail -1
```

Si `tests/test_cli_doctor.py` no existe, usa el fichero de doctor/verify existente y dilo.

## Entrega

Commit en `opencode/iss17`, push y `gh pr create ... --body "... Closes #17 ..."`, **sin mergear**.
Si el harness niega el push, dilo en una línea y espera: Hermes publica.
