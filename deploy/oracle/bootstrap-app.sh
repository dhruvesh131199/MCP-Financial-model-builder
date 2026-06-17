#!/usr/bin/env bash
# Run on Oracle VM as ubuntu AFTER repo is at /opt/financial-models and .env is configured.
# Usage: bash deploy/oracle/bootstrap-app.sh
set -euo pipefail

APP_ROOT="/opt/financial-models"
BACKEND="$APP_ROOT/backend"

if [ ! -f "$BACKEND/.env" ]; then
  echo "ERROR: $BACKEND/.env missing. Copy .env.example and set VIEW_BASE_URL."
  exit 1
fi

cd "$BACKEND"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

sudo cp "$APP_ROOT/deploy/oracle/financial-models-api.service" /etc/systemd/system/
sudo cp "$APP_ROOT/deploy/oracle/financial-models-mcp.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now financial-models-api financial-models-mcp

echo ""
echo "Services:"
sudo systemctl --no-pager status financial-models-api financial-models-mcp || true
echo ""
echo "Next: configure Caddy (see deploy/oracle/Caddyfile.example) and reload caddy."
