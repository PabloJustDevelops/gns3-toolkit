# Verificación por componente

`gns3lab verify` y `gns3_verify` responden a una pregunta distinta de `status` o `doctor`:
¿este componente está **realmente listo**, no solo respondió `200` la API? La comprobación es
**solo de lectura**: no abre proyectos, no arranca nodos y no escribe en pfSense.

## Contrato

```text
usage: gns3lab verify [-h] [--node NODE] [--json] {qemu,pf,vpcs} project
```

- CLI: `gns3lab verify <componente> <proyecto> [--node NOMBRE] [--json]`.
- MCP: `gns3_verify(component, project | project_name | project_id, node=None)`.
- `--node` es opcional; hace falta cuando hay varios nodos del mismo tipo. Sin él, el comando
  falla con la lista de candidatos en vez de elegir uno al azar.
- Si el proyecto está cerrado, devuelve un problema accionable (`gns3lab up <proyecto>` o
  `POST /v2/projects/<id>/open`) y **no lo abre**.

Salida con `--json` (y la misma estructura desde el MCP):

```json
{
  "component": "qemu",
  "project": "examen-kit",
  "ok": false,
  "checks": [
    {"name": "proyecto abierto", "ok": true, "detail": "examen-kit (11111111)"},
    {"name": "estado", "ok": false, "detail": "status=stopped"}
  ],
  "problems": ["estado: status=stopped"],
  "warnings": []
}
```

`ok` es `true` solo si todos los `checks` están en verde. `problems` repite los checks rojos
con su nombre para que un agente no tenga que recorrer el array. `warnings` recoge avisos que
no cambian `ok`: por ejemplo, un nodo pfSense QEMU con consola `vnc`/`spice`, con el comando
para dejarla en `telnet` y la nota de hacerlo con el nodo parado.

## Checks por componente

### `qemu`

| Check | Qué demuestra |
|---|---|
| `estado` | el nodo está `started`, no solo presente |
| `adapter_type` | `properties.adapter_type` está definido |
| `puerto HMP` | hay un `-monitor tcp:…` del proceso QEMU en `/proc` |
| `info status` | el canal HMP responde y dice el estado de la VM |

El puerto se localiza por el `node_id` que GNS3 pasa como `-uuid` a QEMU. En un servidor
remoto `/proc` es del controller, no del compute: el check falla aunque el nodo esté bien.

### `pf` (pfSense)

| Check | Qué demuestra |
|---|---|
| `interfaces` | `pf detect` deduce `wan`/`lan` del `adapter_type`, sin SSH |
| `PFSENSE_PASSWORD` | la variable está definida; solo se comprueba el **nombre**, nunca el valor |
| `config.xml` | se leyó `/conf/config.xml` sin escribir (`cat`, solo lectura) |
| `secciones` | existen `system`, `interfaces`, `filter`, `nat` y `dhcpd` |
| `interfaces configuradas` | `wan`/`lan` de `config.xml` coinciden con las esperadas |
| `reglas` | hay reglas y cada una tiene acción e interfaz válidas |
| `NAT` | el modo de salida es automático, híbrido o manual con reglas |
| `DHCP` | hay rango en LAN, con `from <= to` y dentro de la red de esa interfaz |

Sin `PFSENSE_PASSWORD` no se intenta SSH: los checks de `config.xml` en adelante fallan con un
mensaje que nombra la variable, sin imprimir valores. La comprobación no llama a `put_config`
ni a `/etc/rc.reload_all`.

### `vpcs`

| Check | Qué demuestra |
|---|---|
| `estado` | el nodo está `started` |
| `consola` | la consola telnet acepta conexión y responde a `show ip` |
| `show ip` | hay IP/MASK legible y distinta de `0.0.0.0/0` |
| `gateway` | la gateway existe, no es la máscara y cae en la red de la IP |

VPCS pinta a veces la máscara en el campo `GATEWAY` tras `ip dhcp`; el check lo detecta por el
`.0`/`.255` final y explica cómo fijar la IP a mano con el `DHCP SERVER`. No ejecuta `ip dhcp`
ni `ping`: solo `show ip`.

## Ejemplos

```bash
gns3lab verify qemu examen-kit --json
gns3lab verify pf examen-kit --json
gns3lab verify vpcs examen-kit --node PC1 --json
gns3lab verify vpcs examen-kit --node PC1      # texto: [OK ] / [NO ] por check
```

Códigos de salida: `0` si `ok`, `1` si algún check falla, `2` si el servidor GNS3 no responde.
Con `--json` global (`gns3lab --json verify …`) se conserva el mismo JSON y el mismo código.

## Límites

- No sustituye a `doctor` ni a `test`: `doctor` revisa el entorno y `test` hace ping real.
- `qemu` depende de `/proc`; en un compute remoto no ve el proceso QEMU.
- `pf` necesita SSH y `PFSENSE_PASSWORD` para leer `config.xml`; `detect` sigue funcionando sin
  credenciales. La coherencia es estructural (secciones, interfaces, rangos), no valida que
  pfSense haya recargado ni que el firewall esté pasando tráfico.
- `vpcs` solo lee `show ip`; no comprueba conectividad extremo a extremo.
- Los checks que necesitan servidor, nodos arrancados, proceso QEMU o un pfSense real no se
  pueden demostrar en la suite sin servidor: los tests usan los dobles de `tests/conftest.py`.
  La ejecución contra el laboratorio real queda como comprobación manual.

## Pruebas

```bash
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m pytest -q tests/test_verify_component.py
```

Cubren verde y rojo por check, `--json`, proyecto cerrado, nodo ausente o ambiguo, ausencia de
credenciales en la salida y que `verify` no emite `POST` ni escribe en el firewall.
