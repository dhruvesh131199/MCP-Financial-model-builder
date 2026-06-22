#!/usr/bin/env bash
# Run ON the EC2 instance to debug API/MCP/Caddy reachability.
set -euo pipefail

echo "=== Public IP (update DuckDNS if this changed) ==="
curl -sf http://checkip.amazonaws.com || echo "(checkip failed)"
echo ""

echo "=== systemd ==="
for svc in financial-models-api financial-models-mcp caddy; do
  if systemctl list-unit-files "${svc}.service" &>/dev/null; then
    systemctl is-active "${svc}.service" 2>/dev/null && echo "${svc}: active" || echo "${svc}: NOT active"
  else
    echo "${svc}: not installed"
  fi
done
echo ""

echo "=== Local health (must work before HTTPS) ==="
curl -sf http://127.0.0.1:8000/health && echo " API localhost OK" || echo " API localhost FAILED"
code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/mcp 2>/dev/null || echo "000")
echo " MCP localhost HTTP ${code} (406 is OK)"
echo ""

echo "=== Listening ports ==="
ss -tlnp 2>/dev/null | grep -E ':443|:8000|:8080' || true
echo ""

echo "=== Recent API logs ==="
journalctl -u financial-models-api -n 15 --no-pager 2>/dev/null || true
echo ""

echo "=== Recent MCP logs ==="
journalctl -u financial-models-mcp -n 15 --no-pager 2>/dev/null || true
echo ""

echo "=== Caddy logs ==="
journalctl -u caddy -n 15 --no-pager 2>/dev/null || true
echo ""

echo "=== .env check ==="
ENV_FILE="${HOME}/financial-models/backend/.env"
if [ -f "${ENV_FILE}" ]; then
  grep -E '^VIEW_BASE_URL=|^SEC_USER_AGENT=|^FINNHUB' "${ENV_FILE}" | sed 's/=.*/=…/' || true
else
  echo "MISSING ${ENV_FILE}"
fi
echo ""
echo "If local health OK but https://myfmdc-api.duckdns.org fails:"
echo "  1. DuckDNS A records → public IP above"
echo "  2. EC2 security group inbound 80, 443 from 0.0.0.0/0"
echo "  3. sudo systemctl restart caddy"
