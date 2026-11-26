# BRIEF — carril `pfreload` (issue #13: timeout del reload de pfSense)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-pfreload` · rama `opencode/pfreload`.

## Contexto

El issue #13 del repo documenta un bug real reportado por otro equipo y confirmado aquí:
`gns3lab pf config put` escribe `/conf/config.xml` pero responde `ok: false` con
`timeout tras 20s: ** WARNING: connection is not using a post-quantum key exchange...`.
El reload `/etc/rc.reload_all` tarda **77 s** medidos en pfSense CE 2.7.2, y el cliente corta
a los 20 s de `PfSense.__init__`. Lee `AGENTS.md`, `pfsense.py` (especialmente `__init__` ≈177,
`run` ≈210, `put_config` ≈302 y `_load_and_save`) y `tests/test_pfsense.py`.

## Contrato

1. **`put_config` da timeout propio al reload**: `self.run(reload_command,
   timeout=max(self.timeout, 180))`. El timeout de lectura sigue siendo `self.timeout`.
2. **Timeout del reload ≠ fallo de escritura**: si el reload expira, verifica la configuración
   efectiva antes de decidir. Usa una lectura ligera existente (`get_config()` y/o `pfctl -sr`
   vía `run`). Solo si el cambio está presente devuelve
   `{"ok": True, "reload": "timeout", "backup": ..., "detail": <aviso>}`; si no está, `ok=False`.
   **Nunca** devolver `ok=True` solo porque `config.xml` se escribió.
3. **Filtrar ruido de OpenSSH** en `detail` cuando `returncode == 0`: quita avisos de
   post-quantum key exchange y "known hosts" del stderr; conserva el resto literal.
4. Todas las acciones de escritura pasan por `put_config`: no hace falta cambiarlas una a una.

## Tests (fichero propio `tests/test_pf_reload.py`)

- doble de `run()` con escritura correcta y reload de 77 s → `ok=True`;
- reload timeout + verificación confirma el cambio → `ok=True`, `reload="timeout"`;
- reload timeout + verificación no confirma → `ok=False`;
- stderr con aviso post-quantum y `returncode=0` → `detail` sin el aviso;
- el timeout por defecto de lectura sigue siendo 20 s (no regresión).

## Gates

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-pfreload
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile pfsense.py
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q tests/test_pf_reload.py tests/test_pfsense.py tests/test_cli_pf.py
python3 scripts/verify.py
python3 scripts/check-links.py | tail -1
```

## Entrega (PR, no push a master)

Commit en `opencode/pfreload`, `git push -u origin opencode/pfreload` y
`gh pr create --base master --head opencode/pfreload --title "fix(pfsense): timeout propio para el reload y verificación antes de declarar éxito" --body "... Closes #13 ..."`.
**No mergear**. Si el harness deniega el push, dilo en una línea y espera: Hermes publica.

No toques `gns3core.py`, `gns3_mcp_server.py`, `cli/gns3lab` ni `PROJECT.md`.
