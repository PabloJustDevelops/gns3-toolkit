# SWARM-swcli — auditoría de `cli/gns3lab` (48 comandos)

- **Repo**: `/home/pablorg/Proyectos/gns3-toolkit-wt-swcli` · rama `opencode/swcli` · HEAD `ce2b20e`
- **Alcance**: `cli/gns3lab` únicamente. Foco: argparse, rutas de error, salida `--json`, hooks de
  examen (`_examen_*`, `EXAMEN_MARKER`) y consistencia de comandos.
- **Nada editado**: no se toca código de producción, no se tocan `tests/`, no se hace commit ni PR.
- **Servidor real usado para verificar (solo lectura / 400 sin cambios)**: GNS3 2.2.61 en
  `127.0.0.1:3080`, proyecto abierto `Practica VPN`. No se arranca/para nada, no se crea/borra.
- **Ficheros referenciados**: `cli/gns3lab`. Líneas contra el fichero tal cual está en el worktree.

## Verificación global (evidencia)

```text
$ .venv/bin/python -m py_compile cli/gns3lab          → exit 0
$ .venv/bin/python -m pytest -q                       → 3 failed, 928 passed in 299.73s
  FAILED tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense[None-telnet]
  FAILED tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense[vnc-vnc]
  FAILED tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense[spice-spice]
```

Nota de entorno (no es hallazgo de esta auditoría, corresponde al carril `swtests`): con
`.venv/bin/pytest -q` (sin `-m`) la recolección falla con `ModuleNotFoundError: No module named
'gns3core'` / `'gns3_mcp_server'` porque el `rootdir` no entra en `sys.path`; con
`.venv/bin/python -m pytest -q` se obtienen los 3 fallos de arriba. `AGENTS.md` documenta `pytest -q`.

Los 3 fallos son el **hallazgo #1**. Resto verificado con reproducciones mínimas (dobles locales en
`/tmp`, sin tocar el servidor ni el repo) y, donde se indica, contra el servidor GNS3 real.

---

## Hallazgos priorizados (máx. 10)

### 1. `examen setup` falla por `_examen_disk` que exige `json_list_or_die`, y la suite está roja
**cli/gns3lab:3463-3483** (llamada en **3470** `imagenes = c.json_list_or_die("/v2/computes/local/qemu/images", "imágenes QEMU")`),
introducido en `fb0c10f` "fix: no silenciar errores http en listados (#19)".

- **Impacto concreto**: `_examen_setup` (`cli/gns3lab:3546`) llama a `_examen_disk(c, ...)`. Si `c`
  no implementa `json_list_or_die` (aunque sí `qemu_images()`, que es lo que proveía el camino
  anterior y lo que provee el doble de prueba `tests/test_pf_console.py::ClienteExamenFalso`,
  `qemu_images()` en `tests/test_pf_console.py:267-268`), revienta con
  `AttributeError: 'ClienteExamenFalso' object has no attribute 'json_list_or_die'`. Rompe el hook
  de examen `examen setup` para cualquier cliente que no sea `gns3core.Client` completo, y deja
  **3 tests del repo en rojo**. `gns3core.Client` real sí tiene `json_list_or_die`
  (`gns3core.py:208-213`), así que el servidor en vivo no se ve afectado; lo que falla es el
  contrato interno y la suite.
- **Inconsistencia**: `_templates_or_die` (`cli/gns3lab:1001-1011`) hace
  `if hasattr(c, "json_or_die"): ... else: c.get(...)`. `_examen_disk` no tiene fallback, y
  `_examen_informe` repite `c.json_list_or_die(...)` en `cli/gns3lab:3849`.
- **Reproducir**:
  ```bash
  .venv/bin/python -m pytest -q tests/test_pf_console.py::test_examen_setup_fija_console_type_de_pfsense   # 3 failed
  ```
  ```text
  cli/gns3lab:3470 in _examen_disk
      imagenes = c.json_list_or_die("/v2/computes/local/qemu/images", "imágenes QEMU")
  E   AttributeError: 'ClienteExamenFalso' object has no attribute 'json_list_or_die'
  ```
  Verificación de que conserva la regla "no silenciar HTTP" (la intención de #19) manteniendo
  fallback: usar `c.json_list_or_die(...)` si `hasattr(c,'json_list_or_die')`, `else` `c.qemu_images()`
  / `c.get(...)` con comprobación de `st==200 and isinstance(list)`, nunca `[]` silencioso.

### 2. Acciones irreversibles sin confirmación `_confirm`/`--yes`
**cli/gns3lab** — `_confirm` definido en **637-648** ("Acciones destructivas: exigen `--yes` o
confirmación por TTY"), pero **no** se invoca en estas ramas:

- `node rm` → **2261-2264** (`c.delete(.../nodes/{nid})`, `node borrado=...`).
- `link rm` → **2514-2518** (`c.link_delete(...)`).
- `draw rm` → **2425-2432** (`c.drawing_delete(...)`).
- `snap delete` → **1857-1865** (`c.snapshot_delete(...)`); parser `snap` **4918-4921** sin `--yes`.

Subparsers `node` (**4979-5000**), `link` (**5021-5030**), `draw` (**5007-5014**) **no registran
`--yes`**. Mientras `compute rm` (**738-748**), `template delete` (**1729-1762**), `all` (**2710**),
`disk config` (**2741**), `vm vmnet` (**2776**), `project duplicate` (**3102**), `iou-license set`
(**3338**), `server` (**3353**), `examen reset` (**3784**, `4073`), `console reset-all` (**1951**),
`pf config put` (**4241**, `_pf_config_put_guard` **4232-4244**) sí exigen `_confirm`/`--yes`.

- **Impacto concreto**: `gns3lab node rm PC1`, `gns3lab link rm <id>`, `gns3lab draw rm <id>`,
  `gns3lab snap delete X` borran de inmediato; en no-TTY no hay red de seguridad. Inconsistencia
  con la política propia de `_confirm` y con `compute rm`/`template delete`. `draw rm`/`link rm`/
  `snap delete` no se revierten.
- **Reproducir** (sin tocar servidor real, con doble):
  ```python
  # fake c.delete -> (204, None); no se llama a _confirm; rc=0 y 'borrado=True'
  cli.cmd_node(SimpleNamespace(action='rm', node='X', project='p', server='local', ...), {})
  ```
  Inspección directa: `grep -n '_confirm' cli/gns3lab` no aparece dentro de `cmd_node act=='rm'`,
  `cmd_link rm`, `cmd_draw rm`, `cmd_snap delete`. `./cli/gns3lab node rm --help` no lista `--yes`.

### 3. `exec` deja escapar `core.ConsoleError` (traceback), inconsistente con `console`
**cli/gns3lab:1905-1933** (`cmd_exec`), sólo envuelve `core.console_for` (**1913-1916**); `_core_call`
(**673-685**) sólo convierte `ConnectionError`/`TimeoutError`, no `core.ConsoleError`.

- **Impacto concreto**: `con.wait_ready(...)` (**1918**) y `con.run_many(...)` (**1922-1923**) pueden
  lanzar `core.ConsoleError` (`gns3core.py:919` "la consola se cerró al escribir", `Console.send`
  **913-919**; `wait_ready` → `self.send("\n")`, `run` → `self.send`, `run_many`, `gns3core.py:1039-1045`).
  En modo humano sale un **traceback de Python**, no un error legible `mensaje interno`; el código de
  salida no se controla. `cmd_console` sí lo captura (**2017-2019** `except core.ConsoleError ... return 1`;
  el `--send` **1991-1999** y el interactivo **2015-2019**). (`console reset`/`reset-all`, **1954-1971**,
  usan `_core_call(c.console_reset/nodes_console_reset)`, que sólo envuelve `ConnectionError/TimeoutError`
  y no leen de la consola.) `_examen_verify` captura `core.ConsoleError`, **3775-3777**.
  `exec` es la pieza "consola telnet leída por prompt" y la que más se automatiza.
- **Reproducir** (verificado, salida real):
  ```text
  # _core_target -> nodo started telnet; core.console_for -> Console falso;
  # wait_ready OK; run_many lanza core.ConsoleError
  cmd_exec RAISED ConsoleError : la consola se cerró al escribir: [Errno 32] Broken pipe
  ```
  Con `gns3lab exec` real: apagar/cerrar el nodo o reiniciar la consola a mitad de `run_many`
  (`gns3lab console reset <nodo>` en otra shell) → traceback `gns3core.ConsoleError`.
  Con global `--json`, `_run_handler` (**4671-4677**) lo convierte en `ok:false` + traceback a
  stderr, pero sin `--json` no. Verificación: envolver `wait_ready`+`run_many` en
  `try/except core.ConsoleError -> print(...,stderr); return 1`, como `cmd_console`.

### 4. `lab` en modo humano falla en silencio (sólo `--json` muestra el error)
**cli/gns3lab `_lab_out` 4403-4410**; `cmd_lab` `except errores ... return _lab_out(args, accion, False, {"error": str(exc)})` **4635-4636**;
`L = _lab_module()` **4519** **fuera** del `try`. `errores` incluye `RuntimeError` pero `_lab_module`
(**4379-4396**) ya se evaluó.

- **Impacto concreto**: sin `--json`, `_lab_out(... ok=False ...)` no imprime nada (sólo imprime si
  `_lab_json(args)`; `texto` es `None`) y devuelve `rc=1`. El usuario obtiene **exit 1 sin mensaje**
  pese a que `lab validate` promete "valida el YAML y reporta errores" (`cli/gns3lab:5131`) y a que
  el contrato de `_err`/`AGENTS.md` exige mensaje interno. `_lab_module()` `RuntimeError("no se puede
  importar {ruta}")` **nunca** se captura por `errores`, ni en modo `--json`.
- **Reproducir** (verificado, salida real):
  ```bash
  ./cli/gns3lab lab validate --spec /nonexistent.yaml ; echo $?        # exit 1, sin salida
  printf 'version: 1\nproject: x\nnodes: "no"\n' >/tmp/bad.yaml
  ./cli/gns3lab lab validate --spec /tmp/bad.yaml ; echo $?            # exit 1, sin salida
  ./cli/gns3lab lab validate --spec /tmp/bad.yaml --json               # exit 1, {"ok":false,...,"error":"/tmp/bad.yaml: nodes: lista no vacía obligatoria"}
  ```
  Verificación: en `_lab_out`, en no-json `print(f"ERROR [{accion}]: ...", file=sys.stderr)` cuando
  `ok=False`, o incluir `data.error`; mover `_lab_module()` dentro del `try`.

### 5. `watch --json` añade línea humana a stdout: salida no es JSON
**cli/gns3lab:2870-2920**, `_json_out(evento)` **2910**, `print(f"{eventos} evento(s) en {args.seconds:g} s")` **2917** (stdout).

- **Impacto concreto**: `gns3lab watch --json` emite cero o más documentos JSON de evento y luego
  una línea `N evento(s) en X s` en **stdout** → `json.loads(stdout)` falla
  (`Extra data`); rompe el contrato `--json`. Además, varios eventos = varios documentos JSON
  concatenados (no un array), incompatible con el envoltorio `_run_handler` (`json.loads(texto)`,
  **4681-4691**) que con `--json` global re-envolvería todo como `{"output": "..."}`. Las líneas de
  estado (`WebSocket: ...`, `servidor cerró...`, **2881/2901**) van a stderr (correcto); la línea
  final no.
- **Reproducir** (verificado, salida real):
  ```text
  # un evento JSON + cierre; watch --json
  {"action": "node.started", "event": {"name": "PC1"}}\n1 evento(s) en 0.5 s
  json.loads(stdout) -> JSONDecodeError: Extra data: line 7 column 1 (char 67)
  ```
  ```bash
  ./cli/gns3lab watch --json --seconds 3 -p examen-kit | python3 -m json.tool   # falla
  ```
  Verificación: mandar `N evento(s)` a **stderr**, o envolver salida en `{"events":[...], "count":N}`
  cuando `--json`. Con `watch`, considerar excluir `watch` de la envoltura global `_run_handler`.

### 6. `vm vms --json` emite varios documentos JSON concatenados
**cli/gns3lab:2754-2786**, `_json_out({engine: res})` **2771** dentro de `for engine in elegidos`
(**2765-2774**); `elegidos = list(motores)` = `["virtualbox","vmware"]` si no se pasa `--engine` (**2760**).

- **Impacto concreto**: `gns3lab vm vms --json` (sin `--engine`) imprime `{...virtualbox...}` y
  `{...vmware...}` como **dos JSON separados** → `json.loads(stdout)` falla (`Extra data`). No es
  un objeto único; incompatible con el `_json_out` único por comando y con `_run_handler`.
  `gns3lab vm vms --json --engine virtualbox` sí es válido. Contrasta `cmd_vm` vmnet (un `_json_out`).
- **Reproducir** (verificado, salida real):
  ```text
  rc=0
  {"virtualbox": [{"name": "vb1"}]}\n{"vmware": [{"name": "vmw1"}]}
  json.loads -> JSONDecodeError: Extra data: line 8 column 1 (char 58)
  ```
  ```bash
  ./cli/gns3lab vm vms --json | python3 -m json.tool   # falla si hay ambos motores
  ```
  Verificación: acumular `{engine: res}` y un único `_json_out(objeto)` tras el bucle.

### 7. `examen setup` no verifica la escritura de `EXAMEN_MARKER`, pero `examen reset` la exige
**cli/gns3lab:3651-3656** (`c.project_file_write(pid, EXAMEN_MARKER, json.dumps({...}))`, **retorno
ignorado**); `_examen_reset` **3797-3805** exige `datos.get("created_by")=="gns3lab examen setup"`
y `datos.get("name")==name`. `_examen_informe` lee la misma marca (**3874-3881**, `_pf`-style 3849).
`project_file_write` devuelve `(st, body)`, no `{"ok"...}` (`gns3core.py` `project_file_write`).

- **Impacto concreto**: si `POST /v2/projects/{pid}/files/examen-setup.json` falla (HTTP 5xx,
  permisos, compute caído), `_examen_setup` igual imprime `listo: ... Verifícalo con ...` y
  **devuelve `rc=0`**; `examen reset --name X` luego aborta `'X' no lleva la marca de 'gns3lab
  examen setup'; reset no toca proyectos ajenos`, y `examen informe` marca "no (`examen-setup.json`
  ausente...)". La propia función sí verifica otras escrituras: `core.node_file_write` startup.vpc
  (**3627-3632**, `if not escrito.get("ok")`), `c.drawing_create` (**3643-3647**), y `cmd_project
  file put` (**3164-3175** re-lee), y `_examen_setup` re-lee nodos con `_wait_node_status`
  (**3658-3666**). La marca es un **hook de seguridad** para no resetear proyectos ajenos; que su
  escritura no se compruebe lo debilita. `_examen_reset` además es la única acción que muta sin
  releer, pero depende de la marca.
- **Reproducir** (verificado, salida real; doble con `project_file_write -> (500, {...})`):
  ```text
  rc= 0 ; marker attempted: True -> examen-setup.json ; marker readable: {'error': 'HTTP 404'}
  listo: Kit de examen. Verifícalo con `gns3lab examen verify --name 'Kit de examen'`.
  ```
  Verificación: `st, res = c.project_file_write(...)`, comprobar `st in (200,201,204)` y re-leer
  `c.project_file_read(pid, EXAMEN_MARKER)` y `json.loads`, si no `raise SystemExit(...)`.

### 8. `templates` (sin `--json`) no usa `_err` ni valida forma, y revienta
**cli/gns3lab:1571-1581** `cmd_templates`. `cmd_template list` sí (**1613-1617**).

- **Impacto concreto**:
  - `st != 200` → `print(f"templates -> {st}", stderr); return 1`, **sin `_err(body)`**: se pierde el
    mensaje interno de la API (viola `_err`, `AGENTS.md` "errores con el mensaje interno, no el
    volcado de schema"). Verificado: `GET /v2/templates` 500 `{"message":"boom interno"}` →
    `templates -> 500`.
  - `st==200` pero `body` no es lista (objeto/string) → `for t in body` itera claves y `t.get(...)`
    lanza **`AttributeError`** (traceback; con global `--json`, `_run_handler` lo envuelve pero
    traceback a stderr). Verificado: `(200, {"message":"no es lista"})` → `AttributeError 'str'
    object has no attribute 'get'`. `cmd_template list` comprueba `isinstance(body, list)`.
- **Reproducir**: doble `Server.get -> (500, {...})` / `(200, {...})`; `cli.cmd_templates(...)`.
- **Inconsistencia de salida**: `templates` no tiene `--json` local (a diferencia de `template list`
  **4901-4916**); sólo global `--json`. `AGENTS.md` pide `_err(body)`. Verificación:
  `if st!=200 or not isinstance(body,list): print(f"GET /v2/templates -> [{st}] {_err(body)}",stderr); return 1`.

### 9. Impresión de `body` crudo en errores, saltándose `_err` (volcado de schema)
Varios comandos no pasan el error por `_err` (`cli/gns3lab:2117-2125`) aunque `AGENTS.md` y la propia
docstring de `_err` exigen "mensaje interno, no el volcado de schema anidado":

- `cmd_new` **2109** `print(f"no se pudo crear: [{st}] {body}", stderr)`.
- `node dup` **2270** `print(f"duplicate falló: [{st}] {body}", stderr)`.
- `cmd_upload` **2381** `print(f"subida falló: [{st}] {body}", stderr)`.
- `Server.projects` **422** `raise SystemExit(f"GET /v2/projects -> {st}: {body}")`.
- `Server.nodes` **428** `raise SystemExit(f"nodos de {pid} -> {st}: {body}")`.
- (`cmd_up` **1021-1022** usa sólo `body.get("message")`, no `_err`.)

- **Impacto concreto**: errores de schema/respuesta no-dict se imprimen crudos, muy verbosos y sin
  extraer el mensaje interno; salida no determinista. **Verificado** con `cmd_new`: `409` con
  `{"message": "JSON schema error ... {'message': 'nombre duplicado'}", "status":409}` imprime el
  dict entero; `_err(body)` al menos devuelve sólo `body["message"]` (`msg[:400]`, y ver #10).
  (`_err_literal`, **2128-2132**, es la excepción
  explícita para compute; no aplica aquí.)
- **Reproducir**: `./cli/gns3lab new <nombre-existente>` (409) / forzar `PUT` schema inválido en
  `node dup`; o doble `post -> (4xx, {...})`. Verificación: `_err(body)` en esas líneas.

### 10. `_err` no elimina el volcado de schema nested como promete (regex sólo `"message":` con comillas dobles)
**cli/gns3lab:2117-2125**. `msg = body.get("message")`; si `"JSON schema error" in msg`:
`inner = msg[msg.find("{"):]; re.search(r'"message"\s*:\s*"([^"]+)"', inner)`. Si no casa →
`return str(msg)[:400]`.

- **Impacto concreto**: GNS3 **2.2.61** genera `"JSON schema error with API request '...' and JSON
  data '{...}': <razón real>"`, donde el `{...}` es una **repr Python con comillas simples** y la
  razón va **después** de `}':`, **no** como `"message": "..."` JSON anidado. `_err` no encuentra
  `"message":` → devuelve el mensaje completo truncado a 400 chars, **con el volcado de schema**, en
  contra de su docstring y de `AGENTS.md`. Todos los comandos que usan `_err` (`node props`,
  `template update`, `link edit`, `compute`, `_examen_*`, `_pf_*`, ...) heredan esto.
- **Reproducir** (verificado, salida real, **servidor GNS3 real, acción 400 sin efectos**):
  ```bash
  ./cli/gns3lab node props EquipoLAN -p "Practica VPN" --set console_type=xyz
  # -> EquipoLAN: {'console_type': 'xyz'} -> JSON schema error with API request
  #    '/v2/projects/.../nodes/...' and JSON data '{'console_type': 'xyz'}':
  #    'xyz' is not one of ['vnc','telnet','http','https','spice','spice+agent','none', None]
  ```
  Aquí no hay cambio en el nodo (400 antes de aplicar). `cli._err(body)` devuelve el string
  completo. **La lane `swmcp` ya resuelve esto**: `gns3_mcp_server._err_msg`
  (`gns3_mcp_server.py:185-204`) aplica `re.search(r"\}'\s*:\s*(.+)$", msg, re.S)` y
  `r"['\"]([^'\"]+)['\"]\]"`, y extrae la cola. Verificación: portar esa lógica a `_err` (y un test).

---

## Consistencia / argparse (verificado, no contados como hallazgo separado por el tope de 10)

- **48 comandos** top-level; `handlers` tiene 48 claves (**5164-5182**); todos `sub.add_parser`
  tienen handler. `needs_core` (**5183-5188**) ⊆ `handlers`. Pero `templates` (**4899**) **no** está
  en `needs_core` y no necesita `core` (usa `Server.get`, **1573-1575**). `lab` no está en
  `needs_core` pero `_lab_topologia_servidor` comprueba `core is None` (**4464-4465**); `_lab_module`
  carga `scripts/labspec.py`. (`AGENTS.md` dice 47 comandos; real = 48; otra lane `swtests`.)
- **`--json` inconsistente**: global `--json` (`_run_handler`, **4644-4692**) + `--json` local por
  comando; muchos no tienen `--json` local (`templates`, `snap`, `server`, `port`, `up`, `down`,
  `test`, `fix`, `export`, `import`, `new`, `node add/rm/dup/...` excepto `node links/idlepc`,
  `console`, `exec`, `shot/key/type`, `mon`, `capture`, `capture-port`...); `pf` usa `_pf_out`
  `{ok,data}` (**4100-4108**); `lab` usa `_lab_out` `{ok,action,data}` + `lab_json` (**4399-4410**);
  `examen` mixto; `cmd_examen informe` chequea `global_json or json` (**3963**). Con global `--json`,
  `_run_handler` pasa JSON válido tal cual o envuelve `{"cmd","ok","output"}`; pero hallazgos #5/#6
  rompen `json.loads`. `_confirm` imprime `cancelado` a **stdout** (**646**), no a stderr.
  Además, **global `--json` no implica local `--json`**: `--json` global fija `args.global_json`
  (**4724-4725**), pero `_pf_out` (**4102**), `cmd_watch` (**2909**), `cmd_vm`, `cmd_templates`,
  `cmd_snap`, `_capturas_emit` (**3996**), `_examen_verify_out` (**3673**) comprueban sólo
  `args.json`. `gns3lab --json pf status` sin `--json` local imprime texto que `_run_handler`
  envuelve `{"output":...}`, no `{"ok","data"}`; `gns3lab --json watch` no emite JSON por evento.
  Sólo `_lab_json` (**4399-4400**) y `cmd_examen informe` (**3963**) miran `global_json`.
- **`_err_literal`** (**2128-2132**) sólo para compute/console/nio/disco; resto `_err`.
- **Errores `SystemExit` vs `return 1` vs `print stderr`**: mezcla; `_run_handler` normaliza sólo con
  `--json` global. `_pf_error` `_json_out({"ok":false,...})` stdout + rc1, no stderr (**4111-4116**).
- **`_examen_*`**: `_examen_project` strict sólo `setup`/`reset` (**3403-3422**); `_examen_template`
  pfsense/nat/switch/vpcs (**3425-3446**); `_examen_disks_in_use`, `_examen_disk`,
  `_examen_qemu_path`, `_examen_source`, `_examen_setup`, `_examen_verify(_out)`, `_examen_reset`,
  `_examen_informe`, `_examen_capturas(_consola)`, `cmd_examen`. `EXAMEN_NAME="Kit de examen"`,
  `EXAMEN_MARKER="examen-setup.json"`. `_examen_setup` `console_type` `telnet|vnc|spice` (**5043-5044**,
  **3520-3522**). `_examen_verify` no modifica; `_examen_informe` sólo lectura. Ver hallazgos #1/#7.
- **`console` reserva nombres**: `args.node in ("reset","url","reset-all")` (**1947**); un nodo
  llamado `reset`, `url` o `reset-all` no se puede abrir por `console`. Similarmente `draw`
  `palabras[0].lower()` reserva `list|ls|edit|rm` (**2405-2419**); `gns3lab draw` requiere `nargs="+"`
  (**5008**) así que `if not palabras` (**2406**) es inalcanzable. No se cuenta (bajo impacto).
- **`cmd_import` / `cmd_port` / `cmd_fix`**: `args.no_rename`, `--keep-both`, `_patch_topology`;
  `Server.links` (**426-428**) devuelve `[]` silencioso en no-200 (usado sólo para contar, **1399/1539**).
  `gns3core.Client.links` (**gns3core.py:234-236**) también `[]` silencioso; `cmd_capture`
  (**2566**) usa `c.links(pid)` sin `json_list_or_die`, a diferencia de `cmd_link list` (**2485**);
  `_lab_topologia_servidor` (**4493-4498**) sí comprueba y contrasta `c.links`. No se cuenta (lane
  `swcore` audita `gns3core`, pero la inconsistencia se ve desde `cmd_capture`).
- **`_kv_value`** `json.loads` si se puede (**1582-1587**): `--set name=1` → `int`. Intencional
  ("números, booleanos"). `_set_body` (**971-979**) `k,v=kv.split("=",1)`, `=` sin clave no validado.

## Nada más
Hallazgos reales encontrados: **10** (máximo pedido). No se inventa nada; cada uno cita
`fichero:línea`, impacto concreto y reproducción/verificación. No se escribe código de producción
ni se tocan `tests/`.
