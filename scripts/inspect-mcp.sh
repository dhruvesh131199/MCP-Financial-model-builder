#!/usr/bin/env bash
# Launch MCP Inspector against local financial-models server (Mac/dev only).
# Not used on AWS EC2 — devtools/ is outside EC2 sparse checkout (backend + deploy only).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="${ROOT}/devtools/mcp-inspector/mcp.json"

if [ ! -f "$CONFIG" ]; then
  echo "Missing ${CONFIG}"
  exit 1
fi

if ! curl -sf -o /dev/null -w "%{http_code}" http://localhost:8080/mcp 2>/dev/null | grep -qE '^(200|406)$'; then
  echo "MCP is not running at http://localhost:8080/mcp"
  echo "Start it first:  ./scripts/dev.sh"
  echo "  or:  cd backend && source .venv/bin/activate && python mcp/server.py"
  exit 1
fi

echo "MCP OK at http://localhost:8080/mcp"
echo "Inspector config: ${CONFIG}"
echo "Guide: devtools/mcp-inspector/README.md"
echo ""
echo "For full 10-K tests, set MCP_REQUEST_MAX_TOTAL_TIMEOUT to 1200000 in Inspector Configuration."
echo ""

exec npx @modelcontextprotocol/inspector --config "$CONFIG" --server financial-models
