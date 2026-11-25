# BRIEF — carril `examcli` (montaje de examen en un comando)

Worktree: `/home/pablorg/Proyectos/gns3-toolkit-wt-examcli` · rama `opencode/examcli`.

## Contexto

El kit `examen-kit` ya está montado en local e importado en el aula como
`Pablo Rodriguez Garijo - Kit`. Hoy montarlo en otro servidor exige media docena de comandos.
Hay que convertirlo en **un comando idempotente y seguro con proyectos ajenos**.

Lee `AGENTS.md`, `PROJECT.md`, `cli/gns3lab` (completo), `gns3core.py` y `~/GNS3/CHULETA.md`.
**Usa los métodos del núcleo; no reimplementes HTTP.**

## Contrato

```bash
gns3lab examen setup  [--server local|clase] [--name NOMBRE] [--from PROYECTO_LOCAL]
gns3lab examen verify [--server local|clase] [--name NOMBRE] [--json]
gns3lab examen reset  [--server local|clase] [--name NOMBRE] --yes
```

- `setup`: si ya existe un proyecto con `NOMBRE` (por defecto `Kit de examen`), **no lo borra**;
  informa de que ya está y sale 0. Si no existe, lo crea con pfSense + NAT + switch + 2 VPCS,
  enlaza WAN al NAT y LAN al switch, escribe `startup.vpc` con `ip dhcp` en cada VPCS, y añade
  una nota en el canvas con el direccionamiento. Disco QEMU: usa el que ya exista en el servidor
  y contenga `pfsense` en el nombre, **sin sobrescribir ninguno**; si no hay, lo dice.
- `verify`: comprueba servidor, nodos arrancados, flag `linked_clone`, disco compartido entre
  nodos, NAT presente y salida (`ping 8.8.8.8` desde un VPCS con `--idle 4`). Devuelve un
  resumen con `ok: bool` y `problems: []`; `--json` lo hace parseable.
- `reset`: **solo** para el proyecto creado por `setup` con ese nombre; exige `--yes`; para sus
  nodos y vuelve a arrancarlos. Nunca toca otros proyectos.

`--server clase` usa la config ya corregida a `192.168.71.251`. **No ejecutes `reset` ni
`setup` contra el servidor del aula**: están otros alumnos trabajando. Verifícalos en local
con un nombre de proyecto de prueba y bórralo solo si lo creó tu propia tool.

## Prohibido

No edites `gns3core.py`, `gns3_mcp_server.py`, `tests/`, `docs/`, `README.md` ni `PROJECT.md`.
No `git push`, no PR, no cambio de rama.

## Gates (salida literal)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-examcli
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile cli/gns3lab
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab examen --help | head -8
env -u PYTHONPATH -u VIRTUAL_ENV ./cli/gns3lab examen verify --name examen-kit --json | python3 -m json.tool | head -14
```

Commit: `feat(cli): comando examen setup/verify/reset`. Informa de salida real y de cualquier
proyecto que hayas creado/borrado durante la prueba.
