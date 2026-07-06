#!/usr/bin/env bash
# EC2 only: keep working tree to backend/ + deploy/ (no frontend on disk).
# Safe to run before every git pull. Preserves backend/.env (not in git).
set -euo pipefail

APP_ROOT="${HOME}/financial-models"
BACKEND="${APP_ROOT}/backend"

cd "${APP_ROOT}"

ENV_BACKUP=""
if [ -f "${BACKEND}/.env" ]; then
  ENV_BACKUP="$(mktemp)"
  cp "${BACKEND}/.env" "${ENV_BACKUP}"
fi

git sparse-checkout init --cone
git sparse-checkout set backend deploy

# Re-sync only when extra dirs are on disk (first run or sparse was off)
if [ -d "${APP_ROOT}/frontend" ]; then
  git read-tree -mu HEAD
  rm -rf "${APP_ROOT}/frontend"
  echo "Removed frontend/ from EC2 working tree."
fi

if [ -n "${ENV_BACKUP}" ] && [ -f "${ENV_BACKUP}" ]; then
  cp "${ENV_BACKUP}" "${BACKEND}/.env"
  rm -f "${ENV_BACKUP}"
fi
