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
expect:                    # opcional: comandos de consola por nodo
  pc1:
    - show ip
```

`validate` acumula los errores con la ruta del campo (`nodes[1].ip`,
`links[0].b`, `expect.pc1[0]`) y sale con código 1 si hay alguno.

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
- `apply --yes`: crea el proyecto (`new`), añade nodos (`node add`), aplica
  `adapter_type` (`node props`), crea enlaces (`link add`) y arranca (`up`).
  Sin `--yes` imprime el plan y sale con 2 sin escribir nada. Se detiene en el
  primer fallo y no borra proyectos ni nodos.
- `verify`: sólo lectura. Comprueba con `status` que el proyecto aparece abierto
  y los nodos están `started`, con `link list` que los enlaces existen, con
  `pf detect` el `adapter_type` declarado y con `exec` los comandos de `expect`.
  Si un nodo declara `ip` y es VPCS, ejecuta `show ip` y busca la dirección.
  Devuelve 0 si todo pasa y 1 con el informe por nodo/enlace si algo falla.

`--server/-s` se pasa tal cual a `gns3lab` y aparece también en el plan.

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
- Reutilizar un proyecto existente: `new` falla si el nombre ya está ocupado.
- Borrar ni reiniciar proyectos o nodos.
- Comprobar conectividad entre VPCS más allá de que `exec` responda.
