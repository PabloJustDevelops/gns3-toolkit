# BRIEF — carril `template` (CLI)

Eres un agente de coding. Trabajas SOLO en este worktree:

- Ruta: `/home/pablorg/Proyectos/gns3-toolkit-wt-template`
- Rama: `opencode/template` (ya creada, no cambies de rama)

## Contexto que no se infiere del código

`cli/gns3lab` es una CLI de 22 comandos que habla con un GNS3 2.2 por la API `/v2`. Hay un
servidor real corriendo en `http://127.0.0.1:3080` con los proyectos `Practica VPN` y
`examen-kit`; puedes usarlo para probar, pero **no borres ni crees proyectos** y no toques
`examen-kit` más allá de leer.

Lee antes de escribir: `AGENTS.md`, `PROJECT.md`, `cli/gns3lab` (completo) y `gns3core.py`
(solo lectura, para saber qué hay disponible).

## Problema que resuelve este carril

Hoy no se puede **crear ni editar plantillas** desde la CLI, y por eso no se puede fijar el
puerto `console` (VNC) de un nodo QEMU: el `PUT` sobre el nodo lo ignora y devuelve 200. La
plantilla sí lo acepta. Sin esto, montar un pfSense con un VNC predecible exige la GUI.

## Qué tienes que entregar

Un subcomando `template` en `cli/gns3lab`, con estos verbos y **exactamente estos nombres**
(hay otro carril construyendo la tool MCP con el mismo contrato):

```bash
gns3lab template list [--json]                     # nombre, tipo, template_id, compute
gns3lab template create --from-node PF1 --name "pfSense examen" [--console 5900] [-p PROY]
gns3lab template create --type qemu --name X --set ram=2048 --set hda_disk_image=foo.qcow2
gns3lab template delete <nombre|id> [--yes]
```

- `create --from-node`: `GET` del nodo, se queda con `node_type` y `properties`, y hace
  `POST /v2/templates` con `{name, template_type, compute_id: "local", properties}`.
  Con `--console N` fija `console` **a nivel de plantilla** y lo verifica releyendo.
- `create --type`: sin nodo de origen, con `--set clave=valor` repetible (reutiliza el
  parseo de `node props`, incluido el JSON para números y booleanos).
- `delete`: exige `--yes` cuando stdin no es un TTY; si no, se niega y explica.
- `list --json`: un objeto JSON parseable con `jq`, no una tabla.
- Añade también `doctor --json`: el mismo chequeo, pero serializado (mismo contenido que hoy).

## Reglas de la casa que ya respeta el fichero

- Los errores de la API se muestran con `_err(body)`, nunca con el volcado de schema.
- Los comandos nuevos entran en el dict `handlers` y en `needs_core` si usan `gns3core`.
- Ayuda en español, una línea por comando en el docstring de `main()`.

## Prohibido

- **No edites** `gns3core.py`, `gns3_mcp_server.py` ni nada de `tests/`.
- No toques `README.md`, `docs/`, `PROJECT.md` (los lleva el carril `docs`).
- No `git push`, no PR. No cambies de rama. No borres proyectos ni nodos del servidor.

## Gates (pega la salida real)

```bash
cd /home/pablorg/Proyectos/gns3-toolkit-wt-template
env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python -m py_compile cli/gns3lab
gns3lab --help | grep -A2 template
gns3lab template list
gns3lab doctor --json | python3 -m json.tool | head -20
```

Prueba `template create --from-node PF1 --name "pfSense examen" --console 5900 -p examen-kit`
y **demuestra** con `gns3lab template list --json` que el `console` quedó en 5900. Borra la
plantilla de prueba al terminar (`template delete "pfSense examen" --yes`) y dilo.

## Entrega

Commit en tu rama, mensaje `feat(cli): subcomando template y doctor --json`, y en el informe:
salida literal de los gates, si `console` persistió en la plantilla, y cualquier cosa que la
API rechazara con su mensaje exacto.
