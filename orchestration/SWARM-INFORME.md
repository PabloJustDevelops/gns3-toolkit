# SWARM de auditoría — gns3-toolkit (2026-11-27)

Cinco agentes opencode con **Seaglass Alpha Free**, uno por área, sobre `ce2b20e`. Cada agente
solo leyó código y escribió su informe; no tocó producción ni abrió PRs. Los informes íntegros
están en `orchestration/swarm/`.

| Carril | Área | Informe |
|---|---|---|
| `swcore` | `gns3core.py` (Client/Console/HMP/OCR) | `swarm/SWARM-swcore.md` |
| `swcli` | `cli/gns3lab` (48 comandos) | `swarm/SWARM-swcli.md` |
| `swmcp` | `gns3_mcp_server.py` (50 tools) | `swarm/SWARM-swmcp.md` |
| `swpf` | `pfsense.py` y su documentación | `swarm/SWARM-swpf.md` |
| `swtests` | tests, scripts, capturas y CI | `swarm/SWARM-swtests.md` |

## Verificado por Hermes con salida real

1. **Suite roja por interacción de PRs — RESUELTO.** Los PR #19 y #20 pasaron su CI por
   separado, pero juntos dejaban 3 fallos: `AttributeError: 'ClienteExamenFalso' object has no
   attribute 'json_list_or_die'` en `cli/gns3lab:3470`. Corregido en PR #22 (`2d4ce3f`), CI
   verde. Los cinco agentes lo detectaron de forma independiente.
2. **`rule()` acepta IP/CIDR inválidos** (`pfsense.py:194-200`, `:511-542`). Ejecutado con dobles:
   `pf.rule(src="nope", dst="999.999.999.999/99")` → `ok=True` y XML con
   `<address>nope</address>` y `<network>999.999.999.999/99</network>`. Contrasta con `nat()`
   y `set_ip()`, que sí validan IPv4.
3. **`watch --json` rompe el contrato JSON** (`cli/gns3lab:2917`): tras cada evento con
   `_json_out`, imprime `{N} evento(s) en {X} s` en stdout. `json.loads(stdout)` falla con
   `Extra data`.
4. **`vm vms --json` emite varios documentos** (`cli/gns3lab:2771`): `_json_out` se llama dentro
   del `for engine`, sin `--engine` hay dos objetos separados y `json.loads(stdout)` también
   falla con `Extra data`.
5. **`pytest -q` (script de consola) no arranca**: `5 errors during collection` en 1,20 s
   (`ModuleNotFoundError: No module named 'gns3core' / 'gns3_mcp_server'`). Con
   `python -m pytest -q` funciona. `AGENTS.md` documenta la forma que no funciona.
6. **Deriva de cifras en `AGENTS.md`**: dice 47 comandos y 700 tests; el repo tiene 48 y 931
   colectados. `scripts/verify.py` no escanea `AGENTS.md`.

## Reportado por los agentes, no verificado individualmente por Hermes

- `swcli` hallazgos 2-4 y 7-10: acciones irreversibles sin `--yes`, `ConsoleError` sin manejar
  en `exec`, `lab` modo humano sin error, marker de examen no verificado, `templates` sin
  `--json`, volcado de schema en errores y `_err` con regex incompleta.
- `swpf` hallazgos 2-10: `proto` sin validar, `port` no coaccionado a entero, NAT automático
  con regla sin `target`, `_parse_ifconfig()` en enlaces punto-a-punto, `<filter/>` vacío,
  máscara en `<subnet>`, `<gateway>` con IP cruda, tipos mezclados en `status()` y
  `render_config()` sin preservar comentarios.
- `swmcp`: sin hallazgos en las 50 tools; confirma `verify.py` limpio. Solo reitera la suite
  roja (ya resuelta) y la deriva de `AGENTS.md`.

## Criterio y siguiente acción

Prioridad 1: contrato `--json` de la CLI (es la interfaz para agentes y CI) y validación de
entrada en `pf.rule()` (puede persistir config.xml inválida). Prioridad 2: `AGENTS.md` y el
invocador de pytest, porque cualquier agente nuevo tropieza con ellos. El resto son mejoras
defensivas; cada una debe entrar con su test y su PR, sin lanzarlas en bloque.
