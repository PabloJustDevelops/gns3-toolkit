#!/usr/bin/env python3
"""Smoke del MCP propio en proceso, sin servidor externo.

Pytest lo excluye con `collect_ignore` en `tests/conftest.py`: el modo completo
toca un GNS3 real (arranca nodos, captura tráfico y crea snapshots).

Cómo se lanza a mano:

    .venv/bin/python tests/test_mcp_smoke.py --list   # solo inventario, no toca GNS3
    .venv/bin/python tests/test_mcp_smoke.py          # modo completo (opt-in)

El modo `--list` conecta al objeto `FastMCP` del repo y cuenta tools, recursos y
prompts; no contacta con la API de GNS3. El modo completo hace lo mismo y además
opera sobre el proyecto `lab-prueba`, así que exige GNS3 2.2.x en marcha.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from fastmcp import Client

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gns3_mcp_server  # noqa: E402  (necesita la raíz del repo en sys.path)


def unwrap(r):
    """Extrae el payload de un `CallToolResult` de fastmcp 4.2.6.

    Orden real de la API: `data` (salida estructurada ya deserializada),
    `structured_content` (dict crudo) y, si no hay salida estructurada, el
    primer bloque de texto (JSON o texto plano).
    """
    if r.data is not None:
        return r.data
    if r.structured_content:
        return r.structured_content
    for block in r.content:
        text = getattr(block, "text", None)
        if text is None:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return str(r.content)[:1500]


def show(title, val, limit=900):
    print(f"\n### {title}")
    s = json.dumps(val, ensure_ascii=False, indent=1) if not isinstance(val, str) else val
    print(s[:limit])


async def list_only():
    async with Client(gns3_mcp_server.mcp) as c:
        tools = await c.list_tools()
        resources = await c.list_resources()
        prompts = await c.list_prompts()
    print(f"tools={len(tools)}")
    print(f"resources={len(resources)}")
    print(f"prompts={len(prompts)}")


async def main():
    async with Client(gns3_mcp_server.mcp) as c:
        tools = await c.list_tools()
        print(f"tools={len(tools)}: {[t.name for t in tools]}")

        r = await c.call_tool("gns3_status", {})
        show("status", unwrap(r))

        r = await c.call_tool("gns3_projects", {"action": "list"})
        show("projects", unwrap(r))

        r = await c.call_tool("gns3_templates", {})
        show("templates", unwrap(r))

        r = await c.call_tool("gns3_nodes", {"project_name": "lab-prueba", "action": "list"})
        show("nodes", unwrap(r))

        r = await c.call_tool("gns3_nodes", {"project_name": "lab-prueba", "action": "start", "node": "*"})
        show("start all", unwrap(r))

        r = await c.call_tool("gns3_topology", {"project_name": "lab-prueba"})
        show("topology", unwrap(r))

        await asyncio.sleep(12)

        r = await c.call_tool("gns3_console", {
            "project_name": "lab-prueba",
            "node": "OpenWrt*1",
            "commands": ["ip -4 -o addr show br-lan", "ubus call system board | head -3"],
            "settle": 2.0,
        })
        show("console", unwrap(r))

        r = await c.call_tool("gns3_capture", {
            "project_name": "lab-prueba", "action": "start",
            "node_a": "OpenWrt25.12.6(x86_64)-1", "node_b": "OpenWrt25.12.6(x86_64)-2",
        })
        show("capture start", unwrap(r))

        r = await c.call_tool("gns3_console", {
            "project_name": "lab-prueba", "node": "OpenWrt*2",
            "commands": ["ip addr add 192.168.1.2/24 dev br-lan 2>/dev/null",
                         "ip addr del 192.168.1.1/24 dev br-lan 2>/dev/null",
                         "ip addr add 192.168.1.2/24 dev br-lan",
                         "ping -c 3 192.168.1.1"],
            "settle": 2.5,
        })
        show("ping desde nodo 2", unwrap(r), 1200)

        r = await c.call_tool("gns3_capture", {
            "project_name": "lab-prueba", "action": "stop",
            "node_a": "OpenWrt25.12.6(x86_64)-1", "node_b": "OpenWrt25.12.6(x86_64)-2",
        })
        show("capture stop", unwrap(r))

        r = await c.call_tool("gns3_capture", {
            "project_name": "lab-prueba", "action": "read",
            "node_a": "OpenWrt25.12.6(x86_64)-1", "node_b": "OpenWrt25.12.6(x86_64)-2",
            "summary_lines": 12,
        })
        show("capture read", unwrap(r), 1400)

        r = await c.call_tool("gns3_snapshots", {"project_name": "lab-prueba", "action": "create", "name": "mcp-test"})
        show("snapshot create", unwrap(r), 400)
        r = await c.call_tool("gns3_snapshots", {"project_name": "lab-prueba", "action": "list"})
        show("snapshot list", unwrap(r), 500)

        r = await c.call_tool("gns3_images", {})
        imgs = unwrap(r)
        show("qemu images (primeras)", imgs[:6] if isinstance(imgs, list) else imgs, 600)

        r = await c.call_tool("gns3_server_paths", {})
        show("paths", unwrap(r))


def cli():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true",
                        help="solo inventario de tools/recursos/prompts; no toca GNS3")
    args = parser.parse_args()
    if args.list:
        asyncio.run(list_only())
    else:
        asyncio.run(main())


if __name__ == "__main__":
    cli()
