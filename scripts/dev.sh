#!/usr/bin/env bash
# Start all three services for local HTTP-based dev.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
LOG_DIR="$ROOT/.logs"

# Ports (override via env; MCP_PORT also read from backend/.env when set there)
API_PORT="${API_PORT:-8000}"
FE_PORT="${FE_PORT:-5173}"
MCP_PORT="${MCP_PORT:-}"

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

# Load MCP_PORT from .env when not already set in the shell
if [ -z "${MCP_PORT}" ] && [ -f .env ]; then
  # shellcheck disable=SC2002
  MCP_PORT="$(
    grep -E '^[[:space:]]*MCP_PORT=' .env \
      | tail -1 \
      | cut -d= -f2- \
      | sed -E 's/[[:space:]]+#.*//; s/^[[:space:]]+//; s/[[:space:]]+$//; s/^["'\'']//; s/["'\'']$//'
  )"
fi
MCP_PORT="${MCP_PORT:-8080}"
export MCP_PORT

port_in_use() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

describe_listener() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | awk 'NR==2 {print $1, $2, $9}' || true
}

http_code() {
  # Prints exactly one status code (or 000). Avoids the curl||echo → "000000" bug when
  # connection fails: curl -w still prints 000 and exits non-zero.
  local url="$1"
  curl -s -o /dev/null -w "%{http_code}" --connect-timeout 1 --max-time 2 "$url" 2>/dev/null \
    || true
}

# Vite on macOS often binds only to [::1]; curl to 127.0.0.1 then gets 000. Try both.
frontend_http_code() {
  local port="$1"
  local code
  code=$(http_code "http://127.0.0.1:${port}/")
  if [ "$code" != "000" ] && [ -n "$code" ]; then
    echo "$code"
    return
  fi
  code=$(http_code "http://[::1]:${port}/")
  if [ "$code" != "000" ] && [ -n "$code" ]; then
    echo "$code"
    return
  fi
  code=$(http_code "http://localhost:${port}/")
  echo "${code:-000}"
}

for pair in "API:$API_PORT" "MCP:$MCP_PORT" "frontend:$FE_PORT"; do
  name="${pair%%:*}"
  port="${pair##*:}"
  if port_in_use "$port"; then
    echo "ERROR: Port $port is already in use (needed for $name)."
    echo "  Listening: $(describe_listener "$port")"
    if [ "$name" = "MCP" ] && [ "$port" = "8080" ]; then
      echo ""
      echo "  Often this is another app (e.g. 'cce dashboard --port 8080'), not our MCP."
      echo "  Free the port, or pick another:"
      echo "    MCP_PORT=8081 ./scripts/dev.sh"
      echo "  Then point Cursor MCP at http://localhost:8081/mcp (.cursor/mcp.json)."
    fi
    exit 1
  fi
done

cleanup() {
  echo ""
  echo "Stopping services..."
  kill "$API_PID" "$MCP_PID" "$FE_PID" 2>/dev/null || true
  wait "$API_PID" "$MCP_PID" "$FE_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting API on      http://localhost:${API_PORT}"
uvicorn api.main:app --reload --port "$API_PORT" >"$LOG_DIR/api.log" 2>&1 &
API_PID=$!

echo "Starting MCP on      http://localhost:${MCP_PORT}/mcp"
# MCP has no --reload; restart dev.sh after backend changes to this process.
python mcp/server.py >"$LOG_DIR/mcp.log" 2>&1 &
MCP_PID=$!

echo "Starting frontend on http://localhost:${FE_PORT}"
cd "$ROOT/frontend"
npm install --silent 2>/dev/null || npm install
# --host 127.0.0.1 so IPv4 health checks (and API CORS clients) can reach Vite;
# default Vite on macOS often listens only on [::1].
npm run dev -- --host 127.0.0.1 --port "$FE_PORT" >"$LOG_DIR/frontend.log" 2>&1 &
FE_PID=$!

echo "Waiting for services to start..."
api_ok=0 mcp_ok=0 fe_ok=0
for i in {1..30}; do
  api_ok=0 mcp_ok=0 fe_ok=0
  code=$(http_code "http://127.0.0.1:${API_PORT}/health")
  [ "$code" = "200" ] && api_ok=1

  mcp_code=$(http_code "http://127.0.0.1:${MCP_PORT}/mcp")
  # MCP streamable-HTTP returns 406 for plain GET — that still means the server is up
  { [ "$mcp_code" = "406" ] || [ "$mcp_code" = "200" ]; } && mcp_ok=1

  fe_code=$(frontend_http_code "$FE_PORT")
  { [ "$fe_code" = "200" ] || [ "$fe_code" = "304" ]; } && fe_ok=1

  if [ "$api_ok" = 1 ] && [ "$mcp_ok" = 1 ] && [ "$fe_ok" = 1 ]; then
    echo ""
    echo "All services running:"
    echo "  Dashboard  → http://localhost:${FE_PORT}"
    echo "  MCP        → http://localhost:${MCP_PORT}/mcp"
    echo "  API health → http://localhost:${API_PORT}/health"
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
echo "  API      (port ${API_PORT}): $([ "$api_ok" = 1 ] && echo OK || echo FAIL)  last=$(http_code "http://127.0.0.1:${API_PORT}/health")"
echo "  MCP      (port ${MCP_PORT}): $([ "$mcp_ok" = 1 ] && echo OK || echo FAIL)  /mcp → $(http_code "http://127.0.0.1:${MCP_PORT}/mcp") (want 406)"
echo "  Frontend (port ${FE_PORT}): $([ "$fe_ok" = 1 ] && echo OK || echo FAIL)  last=$(frontend_http_code "$FE_PORT")"
if [ "$mcp_ok" != 1 ]; then
  echo ""
  echo "  Tip: if /mcp returns 404, something else owns MCP_PORT (not FastMCP)."
  echo "  Listener: $(describe_listener "$MCP_PORT")"
fi
if [ "$fe_ok" != 1 ]; then
  echo ""
  echo "  Tip: Vite may be IPv6-only; listener: $(describe_listener "$FE_PORT")"
fi
echo ""
echo "Check logs:"
echo "  tail -20 $LOG_DIR/api.log"
echo "  tail -20 $LOG_DIR/mcp.log"
echo "  tail -20 $LOG_DIR/frontend.log"
tail -5 "$LOG_DIR/api.log" 2>/dev/null || true
tail -5 "$LOG_DIR/mcp.log" 2>/dev/null || true
tail -5 "$LOG_DIR/frontend.log" 2>/dev/null || true
exit 1
