# gns3 MCP — servidor MCP propio para GNS3 2.2 (API v2)

Escrito aquí porque ninguno de los MCP públicos sirve para GNS3 2.2: el mejor mantenido
(`ChistokhinSV/gns3-mcp`) habla **API v3** y solo soporta Windows, y el único con v2
(`Wael-Rd/gns3-mcp-server`) pide usuario y contraseña **en cada llamada**, con 42 tools.

12 tools, credenciales leídas de `~/.config/GNS3/2.2/gns3_server.conf` (nunca viajan en el prompt).

| Tool | Para qué |
|---|---|
| `gns3_status` | versión, computes, proyectos abiertos, rutas |
| `gns3_projects` | list / create / open / close / delete / info |
| `gns3_templates` | plantillas por tipo (qemu, docker, vpcs…) |
| `gns3_nodes` | list / add desde plantilla / start / stop / reload / delete |
| `gns3_links` | list / add / delete |
| `gns3_topology` | resumen legible: nodos, estados, enlaces `A:0/0 <-> B:0/0` |
| `gns3_console` | comandos en la consola telnet del nodo y salida limpia |
| `gns3_capture` | start / stop / read (pcap + resumen `tshark`) |
| `gns3_snapshots` | list / create / restore / delete (`stop_nodes=True` para GNS3) |
| `gns3_images` | imágenes del compute local |
| `gns3_node_files` | leer/escribir ficheros del nodo |
| `gns3_server_paths` | rutas del server y estado de ubridge |

## Detalles de implementación que importan

- **Abre el proyecto solo** si está cerrado (GNS3 devuelve `403 project is not opened`).
- `node` acepta nombre, `*`, `Router*`, `R[12]` o `node_id`; `template` acepta nombre o id.
- `/links/{id}/pcap` responde `409` con la captura ya parada → cae al `.pcap` real en
  `<proyecto>/project-files/captures/` y lo resume con `tshark`.
- Snapshot/restore exigen proyecto parado (`409 Project must be stopped`) → `stop_nodes=True`
  para los nodos, ejecuta y vuelve a arrancar los que estaban `started`.
- FastMCP 4 devuelve las listas como `TextContent` JSON: al consumir el server desde Python,
  parsear `r.content[0].text` cuando `r.data` es `None`.

## Uso

Registrado en Hermes como `gns3` (stdio, `enabled: true`, 12/12 tools):

```bash
hermes mcp list                 # comprobar
hermes mcp test gns3            # handshake + listado de tools
/reload-mcp                     # cargar en la sesión abierta
```

A mano, como cliente:

```bash
cd ~/Applications/gns3-mcp && venv/bin/python test_mcp.py    # batería end-to-end
venv/bin/python gns3_mcp_server.py                            # stdio (lo normal: lo lanza Hermes)
```

Requiere el servidor GNS3 arriba (`gns3` GUI, o `systemctl --user start gns3-server`).

## Verificado (3-nov-2026, GNS3 2.2.61)

`status`, `projects`, `templates`, `nodes/start`, `topology`, `console` (ping real 0 % loss entre
dos OpenWrt), `capture start/stop/read` (6 paquetes ICMP request/reply en el resumen de tshark),
`snapshots create/list/delete` con parada y re-arranque automáticos.
