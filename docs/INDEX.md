# Índice de documentación

Mapa de `docs/`: para qué sirve cada documento, qué parte del código manda y cómo comprobarlo.
Los documentos vivos se mantienen contra el código; los históricos se conservan como se
escribieron.

## Documentos vivos

| Documento | Para qué sirve | Fuente de verdad | Cómo se verifica |
|---|---|---|---|
| [ARQUITECTURA.md](ARQUITECTURA.md) | piezas, clases de `gns3core`, flujo de una orden y por qué consola/HMP | `gns3core.py`, `gns3_mcp_server.py`, `cli/gns3lab` | `python3 scripts/verify.py`; `pytest -q` |
| [COMANDOS.md](COMANDOS.md) | referencia de los 46 subcomandos con flags y ejemplos | `cli/gns3lab` (parser y handlers) | `./cli/gns3lab <cmd> --help`; recuento con `sed -n '2p'` |
| [PARIDAD.md](PARIDAD.md) | qué operación está en CLI, en MCP o en ambos | dict `handlers` y funciones `@mcp.tool` | `scripts/verify.py`; `mcp.list_tools()` |
| [API-COVERAGE.md](API-COVERAGE.md) | endpoint a método, verbo CLI, tool MCP y test | `API_V2_MAP` y `Client` en `gns3core.py` | `scripts/verify.py`; `pytest --collect-only -q` |
| [GUI-PORTADA.md](GUI-PORTADA.md) | operaciones de la GUI con su comando, tool y endpoint | métodos de `Client` y handlers | bloque `Cómo se ha verificado` del propio documento |
| [COMPATIBILIDAD.md](COMPATIBILIDAD.md) | qué se considera cubierto, límites y por qué no hay soporte 3.x | `gns3core.py` y `gns3server` 2.2.61 instalado | `gns3lab status`; `python3 scripts/verify.py` |
| [LIMITES-CONTROLLER-COMPUTE.md](LIMITES-CONTROLLER-COMPUTE.md) | qué rutas son del controller y cuáles del compute, y el significado de 409/500 | `gns3server/web/route.py`, `handlers/api/**` | lectura del `gns3server` instalado; `scripts/verify.py` para enlaces |
| [NIO-Y-CAPTURAS.md](NIO-Y-CAPTURAS.md) | diferencia entre captura de enlace y de puerto, NIO y errores del compute | `port_nio()`, `port_capture()`, `link_capture()` | `pytest -q tests/test_client_nio.py` |
| [EVENTOS.md](EVENTOS.md) | notificaciones HTTP y WebSocket, formato y eventos esperados | `notifications()`, `notifications_ws_url()`, handlers de `gns3server` | `gns3lab watch --seconds 5`; `pytest -q tests/test_mcp_resources.py` |
| [PFSENSE-NATIVO.md](PFSENSE-NATIVO.md) | llevar pfSense por `config.xml` y SSH, con el menú sólo como último recurso | `pfsense.py`, `cli/gns3lab pf` | `pytest -q tests/test_pfsense.py tests/test_cli_pf.py`; `gns3lab pf --help` |
| [MCP-VELOCIDAD.md](MCP-VELOCIDAD.md) | qué hace `gns3_batch`, qué paraleliza y cómo medirlo | `gns3_batch()` y `_batch_is_read_only()` | el bloque `Cómo medirlo` del documento |
| [EXAMEN.md](EXAMEN.md) | guion ordenado del examen, con la salida que confirma cada paso | CLI, `pfsense.py` y `examen` | `gns3lab examen verify`; `gns3lab doctor` |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | síntoma literal, causa y arreglo | mensajes del código y de la API | `grep` del mensaje en el código; `gns3lab doctor` |

## Documentos históricos (no se reescriben)

| Documento | Fecha o naturaleza | Por qué se conserva |
|---|---|---|
| [mcp-README.orig.md](mcp-README.orig.md) | instantánea del 3-nov-2026, doce tools | muestra el estado del MCP antes de este árbol; `scripts/verify.py` lo excluye de los recuentos |
| [research/ubridge-console-enganche.md](research/ubridge-console-enganche.md) | informe del 2026-11-25, REA de `ubridge` | análisis estático con SHA-256 y método propios; se cita, no se edita |

## Fuentes de verdad

| Dato | Dónde vive | Comando |
|---|---|---|
| Número de comandos y nombres | `cli/gns3lab`, dict `handlers` | `./cli/gns3lab --help \| sed -n '2p' \| tr -d ' ' \| tr ',' '\n' \| wc -l` |
| Número de tools y nombres | `gns3_mcp_server.py`, funciones `@mcp.tool` | `grep -c '^@mcp.tool' gns3_mcp_server.py` |
| Áreas de la API | `gns3core.API_V2_MAP` | `python3 scripts/verify.py` |
| Tests | `tests/` | `pytest --collect-only -q` y `pytest -q` |
| Deriva entre docs, skill y código | `scripts/verify.py` | `env -u PYTHONPATH -u VIRTUAL_ENV python3 scripts/verify.py` |
| Enlaces relativos | todos los `.md` de `docs/` | el bloque Python de abajo |

El guard de deriva recuenta las cifras escritas junto a `tools`, `comandos`, `subcomandos`,
`área` o `áreas`, y falla si no coinciden con el AST del código. Por eso los documentos no
repiten un número sin haberlo medido.

## Verificación de enlaces

```bash
python3 - <<'EOF'
import pathlib, re
bad = []
for md in pathlib.Path('docs').rglob('*.md'):
    for link in re.findall(r'\]\((?!http|#)([^)]+)\)', md.read_text()):
        if not (md.parent / link.split('#')[0]).exists():
            bad.append(f'{md}: {link}')
print('enlaces rotos:', bad or 'ninguno')
EOF
```

## Reglas de edición

- Español técnico, sin emoji ni relleno.
- Cada cifra se mide antes de escribirla; si no se puede medir, no se escribe.
- Cada enlace relativo se comprueba con el bloque de arriba.
- `README.md`, `AGENTS.md`, `PROJECT.md`, `skill-sync/**`, `scripts/**`, `.github/**`,
  `orchestration/**` y el código Python tienen otros dueños: no se tocan desde `docs/`.
