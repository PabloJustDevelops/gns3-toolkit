#!/usr/bin/env python3
"""Prueba end-to-end del MCP propio contra el GNS3 2.2.61 local."""
import asyncio
import json

from fastmcp import Client

SERVER = "/home/pablorg/Applications/gns3-mcp/gns3_mcp_server.py"


def unwrap(r):
    """FastMCP 4 devuelve las listas como TextContent JSON, no como structured data."""
    if r.data is not None:
        return r.data
    if r.structured_content:
        return r.structured_content
    try:
        return json.loads(r.content[0].text)
    except Exception:
        return str(r.content)[:1500]


def show(title, val, limit=900):
    print(f"\n### {title}")
    s = json.dumps(val, ensure_ascii=False, indent=1) if not isinstance(val, str) else val
    print(s[:limit])


async def main():
    async with Client(SERVER) as c:
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


asyncio.run(main())
