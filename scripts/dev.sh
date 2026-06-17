#!/usr/bin/env bash
# Start all three services for local HTTP-based dev.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
LOG_DIR="$ROOT/.logs"

mkdir -p "$LOG_DIR"

cd "$BACKEND"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt -q
else
  source .venv/bin/activate
fi

cp -n .env.example .env 2>/dev/null || true

cleanup() {
  echo ""
  echo "Stopping services..."
  kill "$API_PID" "$MCP_PID" "$FE_PID" 2>/dev/null || true
  wait "$API_PID" "$MCP_PID" "$FE_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting API on      http://localhost:8000"
uvicorn api.main:app --reload --port 8000 >"$LOG_DIR/api.log" 2>&1 &
API_PID=$!

echo "Starting MCP on      http://localhost:8080/mcp"
python mcp/server.py >"$LOG_DIR/mcp.log" 2>&1 &
MCP_PID=$!

echo "Starting frontend on http://localhost:5173"
cd "$ROOT/frontend"
npm install --silent 2>/dev/null || npm install
npm run dev >"$LOG_DIR/frontend.log" 2>&1 &
FE_PID=$!

echo "Waiting for services to start..."
for i in {1..15}; do
  api_ok=0 mcp_ok=0 fe_ok=0
  curl -sf http://localhost:8000/health >/dev/null 2>&1 && api_ok=1
  mcp_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/mcp 2>/dev/null || echo "000")
  # MCP returns 406 for plain GET — that still means the server is up
  { [ "$mcp_code" = "406" ] || [ "$mcp_code" = "200" ]; } && mcp_ok=1
  curl -sf http://localhost:5173 >/dev/null 2>&1 && fe_ok=1
  if [ "$api_ok" = 1 ] && [ "$mcp_ok" = 1 ] && [ "$fe_ok" = 1 ]; then
    echo ""
    echo "All services running:"
    echo "  Dashboard  → http://localhost:5173"
    echo "  MCP        → http://localhost:8080/mcp"
    echo "  API health → http://localhost:8000/health"
    echo ""
    echo "Logs: $LOG_DIR/{api,mcp,frontend}.log"
    echo "Press Ctrl+C to stop."
    wait
    exit 0
  fi
  sleep 1
done

echo ""
echo "ERROR: One or more services failed to start."
echo "Check logs:"
echo "  tail -20 $LOG_DIR/api.log"
echo "  tail -20 $LOG_DIR/mcp.log"
echo "  tail -20 $LOG_DIR/frontend.log"
tail -5 "$LOG_DIR/api.log" 2>/dev/null || true
tail -5 "$LOG_DIR/mcp.log" 2>/dev/null || true
tail -5 "$LOG_DIR/frontend.log" 2>/dev/null || true
exit 1
