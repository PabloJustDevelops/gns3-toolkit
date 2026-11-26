# Laboratorio declarativo: ciclo completo

Un YAML pequeño describe el laboratorio deseado. `scripts/labspec.py` lo traduce a órdenes de
`gns3lab` ya existentes: no reimplementa la API, no configura IPs dentro de los nodos y **no
borra nada**. El esquema v1 está en [LAB-SPEC.md](LAB-SPEC.md) y el ejemplo ejecutable en
[lab-ejemplo.yaml](../examples/lab-ejemplo.yaml).

El ciclo es:

```text
validate → export → diff → apply --yes → verify
```

`plan` se intercala entre `validate` y `apply` cuando quieres ver las órdenes antes de escribir.
`apply` sin `--yes` imprime el plan, no escribe nada y **sale con código 2**.

## Estado real de esta rama

Comprobado contra el código de este worktree:

- `python3 scripts/labspec.py --help` lista `validate`, `plan`, `verify`, `apply`.
- `export` y `diff` están **previstos en el carril `dclcore`** (`scripts/labspec.py`).
- `gns3lab lab` con sus seis acciones está **previsto en el carril `dclcli`** (`cli/gns3lab`):
  hoy la CLI no registra ese subcomando, aunque sí tiene `export` para proyectos `.gns3p`.
- La tool `gns3_lab` y las resources `gns3://lab/desired`, `gns3://lab/actual` y
  `gns3://lab/diff` están **previstas en el carril `dclmcp`** (`gns3_mcp_server.py`).

Las órdenes y respuestas que aparecen más abajo siguen el contrato acordado entre carriles.
Los bloques de salida están marcados como **ejemplo ilustrativo**: no son mediciones tomadas en
esta rama.

## Las seis acciones

| Acción | Directa con `labspec.py` | Prevista en la CLI | Toca el servidor |
|---|---|---|---|
| validar | `validate` | `gns3lab lab validate --spec …` | no |
| planificar | `plan` | `gns3lab lab plan --spec …` | no |
| exportar | `export` (previsto) | `gns3lab lab export --project … --out …` | solo lectura; escribe `--out` en local |
| comparar | `diff` (previsto) | `gns3lab lab diff --spec … --topology …` | no, si se pasa `--topology` |
| aplicar | `apply --yes` | `gns3lab lab apply --spec … --yes` | sí |
| verificar | `verify` | `gns3lab lab verify --spec …` | solo lectura |

`diff` y `export` aceptan `--topology <fichero.json>` para poder probarse sin servidor.

## Ejemplo guiado

### 1. `validate`

```bash
python3 scripts/labspec.py validate examples/lab-ejemplo.yaml
```

Salida de ejemplo (ilustrativa, no medida):

```text
OK: lab-ejemplo (3 nodos, 2 enlaces)
```

Acumula errores con la ruta del campo (`nodes[1].ip`, `links[0].b`, `expect.pc1[0]`) y sale con 1
si hay alguno. No habla con el servidor.

### 2. `export`

Parte de una topología real y produce un spec v1 normalizado. `template` se toma de `node_type`
o `template`, y `adapter_type` de `properties`. **Nunca inventa `ip` ni `expect`**: esos campos
siguen escribiéndose a mano. Un enlace sin dos extremos se omite y se reporta en `warn`.

```bash
gns3lab lab export --project lab-ejemplo --out lab.yaml       # previsto en dclcli
python3 scripts/labspec.py export --topology topo.json        # previsto en dclcore
```

La versión de la CLI obtiene nodos y enlaces con `gns3core.Client` y escribe YAML con
`yaml.safe_dump(sort_keys=False)`. Sólo lee el servidor; la única escritura es el fichero local.

### 3. `diff`

Compara el deseado con el actual y devuelve qué falta y qué sobra:

```bash
python3 scripts/labspec.py diff --spec examples/lab-ejemplo.yaml --topology topo.json
gns3lab lab diff --spec examples/lab-ejemplo.yaml --topology topo.json --json
```

Salida de ejemplo (ilustrativa, no medida):

```json
{
  "crear_nodos": [{"name": "pc1", "template": "VPCS", "adapter_type": null}],
  "crear_enlaces": [{"a": "pc1", "b": "sw1", "pa": 0, "pb": 0}],
  "sobrantes_nodos": ["pc-viejo"],
  "sobrantes_enlaces": [],
  "sin_cambios": false
}
```

Compara nodos por nombre y enlaces por `(a, pa, b, pb)` normalizado. `diff(e, e)` da
`sin_cambios: true` con `plan` vacío: esa es la propiedad que hace idempotente el ciclo.

**`sobrantes` se informan, nunca se borran.** Un nodo o enlace que esté en el servidor pero no en
el YAML aparece en el informe; ninguna acción del ciclo lo elimina.

### 4. `plan` (opcional)

```bash
python3 scripts/labspec.py plan examples/lab-ejemplo.yaml
```

Salida de ejemplo (ilustrativa, no medida):

```text
gns3lab new lab-ejemplo
gns3lab node add --template VPCS --name pc1 -p lab-ejemplo
gns3lab node add --template VPCS --name pc2 -p lab-ejemplo
gns3lab node add --template 'Ethernet switch' --name sw1 -p lab-ejemplo
gns3lab link add pc1 sw1 --pa 0 --pb 0 -p lab-ejemplo
gns3lab link add pc2 sw1 --pa 0 --pb 1 -p lab-ejemplo
gns3lab up lab-ejemplo
```

Con `diff`, el plan omite `new` si el proyecto ya existe y sólo crea lo que falta.

### 5. `apply --yes`

```bash
python3 scripts/labspec.py apply --yes examples/lab-ejemplo.yaml
gns3lab lab apply --spec examples/lab-ejemplo.yaml --yes     # previsto en dclcli
```

Crea el proyecto (`new`), añade nodos (`node add`), aplica `adapter_type` (`node props`), crea
enlaces (`link add`) y arranca (`up`). Se detiene en el primer fallo y no borra proyectos ni
nodos. Es la única acción del ciclo que escribe en GNS3: debe reportarse en el informe de la
tarea.

Sin `--yes`, la orden se niega:

```bash
python3 scripts/labspec.py apply examples/lab-ejemplo.yaml
```

Salida de ejemplo (ilustrativa, no medida):

```text
apply escribe en GNS3: repite con --yes (no se ha ejecutado nada)
gns3lab new lab-ejemplo
…
```

Código de salida: 2. En la tool `gns3_lab` (prevista en `dclmcp`), `apply` sin `yes=True`
devuelve `{"ok": false, "error": "…", "plan": [...]}` y no toca nada.

### 6. `verify`

```bash
python3 scripts/labspec.py verify examples/lab-ejemplo.yaml
gns3lab lab verify --spec examples/lab-ejemplo.yaml          # previsto en dclcli
```

Salida de ejemplo (ilustrativa, no medida):

```text
RESULTADO: OK (3 nodos, 2 enlaces)
```

Sólo lectura: `status` para el proyecto y el estado de los nodos, `link list` para los enlaces,
`pf detect` para el `adapter_type` declarado y `exec` para los comandos de `expect`. Si un nodo
declara `ip` y es VPCS, ejecuta `show ip` y busca la dirección. Devuelve 0 si todo pasa y 1 con
el informe por nodo/enlace si algo falla. No abre proyectos ni arranca nodos.

## Qué significa `ip` en el YAML

`ip` es **una expectativa de verificación**, no una orden de escritura. `apply` no configura la
dirección dentro del nodo; `verify` la comprueba con `show ip` en VPCS. Para asignar IPs de
verdad, usa la vía nativa de [PFSENSE-NATIVO.md](PFSENSE-NATIVO.md) o los comandos de consola
de [COMANDOS.md](COMANDOS.md).

## Desde el MCP (previsto en `dclmcp`)

| Recurso / tool | Qué da |
|---|---|
| `gns3://lab/desired` | spec validada y normalizada; lee la ruta de `GNS3_LAB_SPEC` |
| `gns3://lab/actual` | topología resumida del proyecto declarado en `desired` |
| `gns3://lab/diff` | `diff` más el plan en órdenes legibles; solo lectura |
| `gns3_lab(action=…)` | `validate\|plan\|diff\|apply\|export\|verify`, delegando siempre en `labspec` |

Si `GNS3_LAB_SPEC` no está definida o el fichero no existe, `gns3://lab/desired` responde
`{"error": "…", "hint": "define GNS3_LAB_SPEC"}`; nunca inventa una ruta. `validate`, `plan`,
`diff` y `export` con `topology` dado funcionan sin servidor.

## Comprobación en esta rama

```bash
python3 scripts/labspec.py --help          # validate, plan, verify, apply
python3 scripts/check-links.py             # OK: sin enlaces rotos
gns3lab --help                             # no registra `lab` todavía
```

Mapa de documentación y estado de cada pieza en [INDEX.md](INDEX.md); referencia de comandos en
[COMANDOS.md](COMANDOS.md); reglas de edición y límites en [LAB-SPEC.md](LAB-SPEC.md).
