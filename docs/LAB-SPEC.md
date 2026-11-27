# Lab declarativo (`scripts/labspec.py`)

Un fichero YAML describe el laboratorio deseado y `labspec.py` lo traduce a
órdenes de la CLI existente. No reimplementa la API ni borra nada.

## Esquema

```yaml
version: 1                 # obligatorio, entero 1
project: lab-ejemplo       # obligatorio, nombre seguro (letras, dígitos, . _ -)
nodes:                     # lista no vacía
  - name: pc1              # obligatorio, único en el fichero
    template: VPCS         # nombre o id de plantilla del servidor
    adapter_type: e1000    # opcional; se aplica con `node props`
    ip: 10.0.0.11/24       # opcional; verify la comprueba, apply NO la configura
links:                     # lista (puede estar vacía)
  - a: pc1
    b: sw1
    pa: 0                  # adapter del primer nodo (por defecto 0)
    pb: 0                  # adapter del segundo nodo (por defecto 0)
    porta: 2               # opcional: puerto del primer nodo (por defecto 0)
    portb: 3               # opcional: puerto del segundo nodo (por defecto 0)
expect:                    # opcional: comandos de consola por nodo
  pc1:
    - show ip
# previsto en capcore: capturas por fase (máximo 5)
# captures:
#   - phase: topologia
#     after: apply          # apply | verify
#     node: null            # o nombre de nodo con monitor HMP
```

`validate` acumula los errores con la ruta del campo (`nodes[1].ip`,
`links[0].b`, `expect.pc1[0]`) y sale con código 1 si hay alguno. El campo `ip` sigue siendo
sólo una expectativa de verificación: `apply` no lo configura dentro del nodo; `verify` lo
comprueba con `show ip` cuando es VPCS. `porta` y `portb` son opcionales: si faltan valen 0,
`export` los omite cuando el puerto real es 0, `diff` los compara y `plan` añade `--ppa/--ppb`
sólo cuando están declarados.

## Perfil de pfSense

El bloque opcional `pfsense:` describe la instancia de pfSense del laboratorio. Es el contrato
que consume `gns3lab pf profile` (carril core) y que ya lee la puerta WebUI de este árbol:

```yaml
pfsense:
  node: PF1
  lan_cidr: 192.168.1.0/24
  pfsense_ip: 192.168.1.1
  dhcp_from: 192.168.1.100
  dhcp_to: 192.168.1.200
  wan: NAT1
  adapter_type: e1000
  console_type: telnet
  bridge: br-gns3-ejemplo-a
  host_ip: 192.168.1.254
  webui_name: pfsense-ejemplo-a
```

`webui_name` es el nombre estable con el que se abre la WebUI y `pfsense_ip` la dirección real
del firewall. `webui_port` es opcional (443 por defecto). No se escriben credenciales: la
contraseña sigue viniendo de `PFSENSE_PASSWORD`.

Los dos ejemplos de `examples/pf-perfiles/` usan subredes distintas
(`192.168.1.0/24` y `192.168.10.0/24`) y nombres distintos
(`pfsense-ejemplo-a`, `pfsense-ejemplo-b`), así que pueden convivir. Una sola puerta local los
publica:

```bash
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python scripts/pf_webui_proxy.py \
  examples/pf-perfiles/ --port 8080
# http://127.0.0.1:8080/pfsense-ejemplo-a/
# http://127.0.0.1:8080/pfsense-ejemplo-b/
```

El proxy sólo acepta el certificado autofirmado del firewall; el núcleo no relaja TLS. La
consola telnet sigue siendo la vía para configurar (`gns3lab pf`), y la WebUI del controller GNS3
—`GET /v2/servers` → `404` en 2.2.61— es un problema separado que este perfil no toca. En este
árbol `scripts/labspec.py` todavía no interpreta el bloque `pfsense:`: lo aplica el comando
`pf profile` del carril core.

## Comandos

```bash
python scripts/labspec.py validate examples/lab-ejemplo.yaml
python scripts/labspec.py plan examples/lab-ejemplo.yaml
python scripts/labspec.py apply --yes examples/lab-ejemplo.yaml
python scripts/labspec.py verify examples/lab-ejemplo.yaml
```

- `validate`: lee el YAML con `yaml.safe_load` y valida esquema, referencias y
  direcciones IP. No habla con el servidor.
- `plan`: imprime las órdenes `gns3lab` que se ejecutarían, sin ejecutarlas.
- `apply --yes` directo: crea el proyecto (`new`), añade nodos (`node add`), aplica
  `adapter_type` (`node props`), crea enlaces (`link add`) y arranca (`up`). Sin `--yes`
  imprime el plan y sale con 2 sin escribir nada. Se detiene en el primer fallo y no borra
  proyectos ni nodos. La vía idempotente es `gns3lab lab apply`, que compara con la topología
  real y sólo arranca al crear el proyecto.
- `verify`: sólo lectura. Comprueba con `status` que el proyecto aparece abierto
  y los nodos están `started`, con `link list` que los enlaces existen, con
  `pf detect` el `adapter_type` declarado y con `exec` los comandos de `expect`.
  Si un nodo declara `ip` y es VPCS, ejecuta `show ip` y busca la dirección.
  Devuelve 0 si todo pasa y 1 con el informe por nodo/enlace si algo falla.

`--server/-s` se pasa tal cual a `gns3lab` y aparece también en el plan.

### Capturas por fase (previsto en capcore)

El campo opcional `captures` no está activo en este árbol. El contrato previsto añade entradas
`{phase, after, node}` con `after` igual a `apply` o `verify`, un máximo de 5 fases y un error con
la ruta del campo (`captures[0].after`) si falta el nombre o el momento. Con `captures=True`,
`aplicar_deseado` y `verificar` capturan por HMP tras la fase correspondiente; un fallo de captura
se reporta en el resultado y no cambia el exit code del montaje. La orden prevista es
`gns3lab lab apply --spec … --captures --yes` (el flag `--captures` no está hoy en
`./cli/gns3lab lab apply --help`). El índice resultante y las reglas de la WebUI están en
[CAPTURAS-EXAMEN.md](CAPTURAS-EXAMEN.md).

### `export` y `diff` (implementados)

En este árbol `scripts/labspec.py` no los registra todavía (`--help` lista `validate`, `plan`,
`verify`, `apply`). El contrato implementado añade dos subcomandos al fichero, `export` y `diff`, sin
ampliar opcionalmente el esquema v1:

- `export(topology, project=None) -> dict`: convierte una topología real en un spec v1
  normalizado y válido. `template` se toma de `node_type` o `template`, `adapter_type` de
  `properties`; los enlaces pasan a `{a, b, pa, pb}` y añaden `porta`/`portb` sólo cuando
  `port_number` no es 0. Nunca inventa `ip` ni `expect`. Un enlace sin dos extremos se omite y
  se reporta en `warn`, sin lanzar excepción. Disponible como `python3 scripts/labspec.py export --topology topo.json` (o `--stdin`) y
  como `gns3lab lab export --topology topo.json`.
- `diff(deseado, actual) -> dict`: devuelve `crear_nodos`, `crear_enlaces`, `sobrantes_nodos`,
  `sobrantes_enlaces` y `sin_cambios`. Compara por nombre de nodo y por
  `(a, pa, porta, b, pb, portb)` normalizado, con los puertos ausentes valiendo 0.
  `diff(e, e)` da `sin_cambios: true` y plan vacío. Disponible como `python3 scripts/labspec.py diff --spec … --topology topo.json` y
  `gns3lab lab diff --spec … --topology topo.json`, con `--json` opcional.

Los `sobrantes` **se informan, nunca se borran**: ni `diff` ni `apply` eliminan nodos ni
enlaces del servidor. `plan(deseado, actual)` omite `new` y `up` si el proyecto existe y sólo
crea lo que falta; `aplicar_deseado` sin `yes` imprime el plan y sale con 2.

### Subcomando `gns3lab lab` (implementado)

`cli/gns3lab` registra hoy `export` para proyectos `.gns3p`, pero no `lab`. El carril `dclcli`
añadirá `gns3lab lab <acción> [--json]` con seis acciones, todas delegadas en `labspec`:

| Acción | Ejemplo |
|---|---|
| `validate` | `gns3lab lab validate --spec examples/lab-ejemplo.yaml` |
| `plan` | `gns3lab lab plan --spec examples/lab-ejemplo.yaml` |
| `diff` | `gns3lab lab diff --spec … --topology topo.json` |
| `apply` | `gns3lab lab apply --spec … [--topology topo.json] --yes` |
| `verify` | `gns3lab lab verify --spec …` |
| `export` | `gns3lab lab export --project lab-ejemplo --out lab.yaml` |

`--json` devuelve `ok`, `action` y `data`; en `apply` sin `--yes` devuelve `ok=false` y el plan.
`export` lee la topología con `gns3core.Client` y escribe YAML en local; es la única parte que
necesita servidor. El ciclo completo y la salida de ejemplo están en
[LAB-DECLARATIVO.md](LAB-DECLARATIVO.md).

Ejemplo completo: [lab-ejemplo.yaml](../examples/lab-ejemplo.yaml) (dos VPCS y
un switch, sin pfSense).

## Qué hace y qué no hace

Hace:

- Validar un formato pequeño, versionado y legible.
- Enseñar el plan exacto antes de tocar el servidor.
- Aplicar el laboratorio con subcomandos ya existentes.
- Verificar el resultado con lecturas, sin VNC.

No hace:

- Configurar IPs, DHCP, VLANs ni pfSense dentro de los nodos: `ip` es una
  expectativa de verificación, no una orden de escritura.
- Crear plantillas, imágenes o discos; la plantilla debe existir en el servidor.
- Hacer idempotente el `apply` directo de `labspec.py`: conserva la creación de la v1
  original. `gns3lab lab apply` sí reutiliza un proyecto existente sin arrancarlo.
- Borrar ni reiniciar proyectos o nodos.
- Comprobar conectividad entre VPCS más allá de que `exec` responda.
