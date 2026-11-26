# BRIEF — carril `monfix` (issue #14: `gns3lab mon` revienta con TypeError)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-monfix` · rama `opencode/monfix`.

## Contexto

El issue #14 del repo documenta el bug reportado por otra máquina, confirmado aquí en
`b5b8641`: `cli/gns3lab:4932` declara `add_argument("cmd", nargs="+")` dentro del subparser
`mon`, y `cli/gns3lab:5146` hace `args.cmd in needs_core`. Como `args.cmd` es una lista, la
pertenencia al `set` lanza `TypeError: unhashable type: 'list'` antes de llegar al handler.
Lee `AGENTS.md`, `cli/gns3lab` (`cmd_mon` ≈2091, subparser ≈4930, `main()` ≈5146) y los tests
de CLI existentes.

## Contrato

1. Renombrar el posicional de `mon` de `cmd` a `command` (`nargs="+"`) en el subparser.
2. Ajustar `cmd_mon` para usar `args.command` y unirlo con `" ".join(args.command)` al enviarlo
   al monitor HMP. Mantener `--json`, `-p/--project` y la resolución del nodo.
3. `args.cmd` debe seguir siendo el nombre del subcomando (`"mon"`) para `handlers`/`needs_core`.
4. Test nuevo en `tests/test_cli_mon.py`: invocar `main(["mon", ...])` con dobles de
   `gns3core.Client`/`QemuMonitor` (sin QEMU real) y comprobar que:
   - no hay `TypeError`;
   - el comando enviado al monitor es `"info status"` (una sola cadena);
   - `--json` devuelve un objeto parseable.
   Añade también una comprobación de que ningún otro subparser declara un posicional `cmd`.

## Gates

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-monfix
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile cli/gns3lab
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q tests/test_cli_mon.py tests/test_cli_lab.py tests/test_qemu.py
python3 scripts/verify.py
python3 scripts/check-links.py | tail -1
```

## Entrega (PR, no push a master)

Commit en `opencode/monfix`, `git push -u origin opencode/monfix` y
`gh pr create --base master --head opencode/monfix --title "fix(cli): mon usa command y ya no colisiona con args.cmd" --body "... Closes #14 ..."`.
**No mergear**. Si el harness niega el push, dilo en una línea y espera: Hermes publica.

No toques `gns3core.py`, `pfsense.py`, `gns3_mcp_server.py`, `PROJECT.md` ni `README.md`.
