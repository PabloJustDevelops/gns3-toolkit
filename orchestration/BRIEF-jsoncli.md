# BRIEF — carril `jsoncli` (salida JSON uniforme en la CLI)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-jsoncli` · rama `opencode/jsoncli`.

## Contexto

Varios comandos tienen `--json` propio, pero no todos. Un agente o CI quiere una única forma de
obtener salida parseable sin conocer cada comando. Lee `AGENTS.md`, `PROJECT.md`, `cli/gns3lab`
(completo) y `gns3core.py`.

## Contrato

1. **`--json` global**, antes del subcomando: `gns3lab --json status`, `gns3lab --json doctor`,
   etc. Debe funcionar para **todos** los comandos sin reescribir cada handler:
   - En `main()`, detecta el flag y envuelve la ejecución del handler capturando `stdout`.
   - Si lo capturado ya es JSON válido, lo imprime tal cual.
   - Si no, lo envuelve como `{"cmd": <subcomando>, "ok": <bool>, "output": <texto>}`.
   - `stderr` no se captura. El exit code del handler se conserva.
   - Si un comando ya tenía `--json` local, el global no debe romperlo (doble JSON es error).
2. **`gns3lab examen informe [--server local|clase] [--name NOMBRE] [--dest RUTA]`** — genera
   un informe Markdown con topología, estado, nodos, enlaces y comprobaciones realizadas por
   `gns3core` (sin inventar resultados). Escribe en `~/GNS3/informes/` y devuelve la ruta por
   stdout; con `--json` global devuelve `{"path", "bytes", "ok"}`. No incluye credenciales.
3. Actualiza el docstring de `main()` y la ayuda con los dos cambios.

## Prohibido

No edites `gns3core.py`, `gns3_mcp_server.py`, `tests/`, `docs/`, `README.md` ni `PROJECT.md`.
No `git push`, no PR, no cambio de rama. No ejecutes `examen reset` ni acciones destructivas
contra servidores reales.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-jsoncli
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile cli/gns3lab
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab --json status | python3 -m json.tool | head -8
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab --json doctor examen-kit | python3 -m json.tool | head -8
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab examen informe --name examen-kit | head -4
```

Commit: `feat(cli): --json global e informe de examen`. Informa de salida real.
