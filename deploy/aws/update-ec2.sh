#!/usr/bin/env bash
# Pull latest backend code on EC2 and restart API + MCP.
# Usage: bash ~/financial-models/deploy/aws/update-ec2.sh
set -euo pipefail

APP_ROOT="${HOME}/financial-models"
BACKEND="${APP_ROOT}/backend"

cd "${APP_ROOT}"
git pull

source "${BACKEND}/.venv/bin/activate"
pip install -r "${BACKEND}/requirements.txt" -q

if systemctl is-active --quiet financial-models-api 2>/dev/null; then
  sudo systemctl restart financial-models-api financial-models-mcp
  echo "Restarted financial-models-api and financial-models-mcp."
else
  echo "systemd services not installed. Run: bash deploy/aws/install-systemd.sh"
fi

api_ok=0
for i in 1 2 3 4 5; do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    api_ok=1
    break
  fi
  sleep 2
done

if [ "$api_ok" = 1 ]; then
  echo " API OK"
else
  echo " API not responding — run: bash deploy/aws/diagnose-ec2.sh"
  journalctl -u financial-models-api -n 20 --no-pager 2>/dev/null || true
fi
