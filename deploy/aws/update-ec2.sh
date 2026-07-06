#!/usr/bin/env bash
# Pull backend on EC2 and restart API + MCP. Frontend lives on Render only.
# Usage: bash ~/financial-models/deploy/aws/update-ec2.sh
set -euo pipefail

APP_ROOT="${HOME}/financial-models"
BACKEND="${APP_ROOT}/backend"
DEPLOY="${APP_ROOT}/deploy/aws"
# Must match Render VITE_APP_URL exactly (see deploy/production-urls.txt)
RENDER_APP_URL="${RENDER_APP_URL:-https://financial-model-dashboard.onrender.com}"

cd "${APP_ROOT}"

bash "${DEPLOY}/ensure-sparse-checkout.sh"

echo "Pulling backend + deploy only..."
git pull

bash "${DEPLOY}/ensure-venv.sh"

ENV_FILE="${BACKEND}/.env"
if [ ! -f "${ENV_FILE}" ]; then
  echo "ERROR: ${ENV_FILE} missing. Copy from .env.example and set VIEW_BASE_URL=${RENDER_APP_URL}"
  exit 1
fi

if grep -qE '^VIEW_BASE_URL=(http://localhost|http://127\.0\.0\.1)' "${ENV_FILE}" 2>/dev/null; then
  echo "WARNING: VIEW_BASE_URL is localhost — browser CORS will fail."
  echo "  Set VIEW_BASE_URL=${RENDER_APP_URL} in ${ENV_FILE}"
fi

if systemctl list-unit-files financial-models-api.service --no-legend 2>/dev/null | grep -q financial-models-api; then
  sudo systemctl restart financial-models-api financial-models-mcp
  echo "Restarted API + MCP."
else
  echo "Run once: bash ${DEPLOY}/install-systemd.sh"
fi

curl -sf http://127.0.0.1:8000/health >/dev/null && echo "API OK" || echo "API not up — bash ${DEPLOY}/diagnose-ec2.sh"

if [ -d "${APP_ROOT}/frontend" ]; then
  echo "WARNING: frontend/ still on disk — re-run ensure-sparse-checkout.sh"
else
  echo "Sparse checkout OK."
fi
