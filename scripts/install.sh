#!/usr/bin/env bash
# Instalación idempotente: venv, dependencias y symlink de la CLI.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

PY=python3.12
command -v uv >/dev/null || { echo "falta uv (https://docs.astral.sh/uv/)"; exit 1; }

if [ ! -d .venv ]; then
  echo "→ creando venv con $PY"
  uv venv .venv --python 3.12
fi

echo "→ instalando dependencias"
env -u PYTHONPATH -u VIRTUAL_ENV uv pip install --python .venv/bin/python \
  fastmcp httpx pillow pytest >/dev/null

mkdir -p "$HOME/.local/bin"
ln -sfn "$REPO/cli/gns3lab" "$HOME/.local/bin/gns3lab"
echo "→ CLI enlazada: $HOME/.local/bin/gns3lab"

python3 -m py_compile gns3core.py gns3_mcp_server.py cli/gns3lab
echo "→ compila"

if [ -x "$REPO/.venv/bin/python" ]; then
  echo "→ tools del MCP:"
  env -u PYTHONPATH -u VIRTUAL_ENV "$REPO/.venv/bin/python" - <<'EOF'
import asyncio, sys
sys.path.insert(0, ".")
import gns3_mcp_server as s
tools = asyncio.run(s.mcp.list_tools())
print(f"   {len(tools)} tools: {', '.join(t.name for t in tools)}")
EOF
fi

command -v tesseract >/dev/null || echo "aviso: sin tesseract, 'gns3lab shot' no dará texto"
echo
echo "Listo. Para registrar el MCP en Hermes:"
echo "  hermes mcp add gns3 --command $REPO/.venv/bin/python --args $REPO/gns3_mcp_server.py"
