# Laboratorio declarativo (referencia corta)

Un YAML describe el laboratorio deseado y `scripts/labspec.py` lo convierte en órdenes de
`gns3lab`. **No borra nada**: los `sobrantes` que detecte `diff` se informan, nunca se eliminan.

## Seis acciones

| Acción | Orden | ¿Escribe en GNS3? |
|---|---|---|
| validar | `gns3lab lab validate --spec lab.yaml` | no |
| planificar | `gns3lab lab plan --spec lab.yaml` | no |
| exportar | `gns3lab lab export --project lab-ejemplo --out lab.yaml` | no (sólo `--out` en local) |
| comparar | `gns3lab lab diff --spec lab.yaml --topology topo.json` | no |
| aplicar | `gns3lab lab apply --spec lab.yaml --yes` | sí |
| verificar | `gns3lab lab verify --spec lab.yaml` | no (solo lectura) |

Ciclo: `validate → export → diff → apply --yes → verify`. **`apply` sin `--yes` no escribe nada
y sale con 2**; en el MCP devuelve `{"ok": false, "error": "…", "plan": [...]}`.

`ip` en el YAML es una expectativa de `verify`, no una orden de configuración: `apply` no
asigna IPs dentro de los nodos.

Las seis acciones del subcomando `lab` están **previstas en el carril `dclcli`**; `export` y
`diff` en `labspec.py`, en el **`dclcore`**; la tool `gns3_lab` y las resources, en el
**`dclmcp`**. Si `gns3lab lab --help` no existe todavía, usa las órdenes directas:
`python3 scripts/labspec.py validate|plan|apply|verify lab.yaml`.

## Desde el MCP

- `GNS3_LAB_SPEC` debe apuntar al fichero YAML. Si no está definida o el fichero falta,
  `gns3://lab/desired` responde `{"error": "…", "hint": "define GNS3_LAB_SPEC"}`: nunca inventa
  una ruta.
- Resources previstas: `gns3://lab/desired`, `gns3://lab/actual`, `gns3://lab/diff` (esta última
  añade el plan y es de solo lectura).
- Tool prevista: `gns3_lab(action="validate|plan|diff|apply|export|verify", …)`, siempre
  delegada en `labspec`.

## Reglas de la skill

- El VNC es el último recurso: consola telnet (`exec`) y luego monitor HMP (`shot`/`type`/`key`).
- Nunca escribas credenciales ni contraseñas en el repo ni en un markdown.
- Reporta cualquier cambio de estado (`apply`, `up`, `down`, `examen reset`) en el informe final.
- Verifica con salida real: `0% packet loss`, `doctor` sin hallazgos u OCR legible; un `200 OK`
  de la API no prueba nada.

Guía completa: [docs/LAB-DECLARATIVO.md](../../docs/LAB-DECLARATIVO.md); esquema y límites:
[docs/LAB-SPEC.md](../../docs/LAB-SPEC.md); reglas de la skill: [SKILL.md](../SKILL.md).
