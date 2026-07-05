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

echo "Enabling sparse checkout (backend + deploy only)..."
git sparse-checkout init --cone
git sparse-checkout set backend deploy

# Apply sparse tree and remove previously checked-out frontend files
git read-tree -mu HEAD

if [ -d "${APP_ROOT}/frontend" ]; then
  rm -rf "${APP_ROOT}/frontend"
  echo "Removed frontend/ from EC2."
fi

echo "Done. Future git pull will only update:"
git sparse-checkout list
