#!/usr/bin/env bash
# One-time on EC2: only checkout backend + deploy scripts (skip frontend).
# Usage: bash ~/financial-models/deploy/aws/setup-sparse-checkout.sh
set -euo pipefail

APP_ROOT="${HOME}/financial-models"

if [ ! -d "${APP_ROOT}/.git" ]; then
  echo "Expected git repo at ${APP_ROOT}"
  exit 1
fi

cd "${APP_ROOT}"

ENV_BACKUP=""
if [ -f "${APP_ROOT}/backend/.env" ]; then
  ENV_BACKUP="$(mktemp)"
  cp "${APP_ROOT}/backend/.env" "${ENV_BACKUP}"
  echo "Backed up backend/.env (not in git — preserved across sparse checkout)."
fi

echo "Enabling sparse checkout (backend + deploy only)..."
git sparse-checkout init --cone
git sparse-checkout set backend deploy

# Apply sparse tree and remove previously checked-out frontend files
git read-tree -mu HEAD

if [ -n "${ENV_BACKUP}" ] && [ -f "${ENV_BACKUP}" ]; then
  cp "${ENV_BACKUP}" "${APP_ROOT}/backend/.env"
  rm -f "${ENV_BACKUP}"
  echo "Restored backend/.env"
fi

if [ -d "${APP_ROOT}/frontend" ]; then
  rm -rf "${APP_ROOT}/frontend"
  echo "Removed frontend/ from EC2."
fi

if [ ! -f "${APP_ROOT}/backend/.env" ]; then
  echo ""
  echo "WARNING: backend/.env is missing. Create it before starting services:"
  echo "  cp backend/.env.example backend/.env"
  echo "  nano backend/.env   # set VIEW_BASE_URL, SEC_USER_AGENT, DATABASE_URL, etc."
fi

echo "Done. Future git pull will only update:"
git sparse-checkout list
