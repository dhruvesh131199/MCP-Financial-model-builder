#!/usr/bin/env bash
# Create or reuse backend Python venv (3.11 preferred on Amazon Linux).
# Usage: bash deploy/aws/ensure-venv.sh
set -euo pipefail

APP_ROOT="${HOME}/financial-models"
BACKEND="${APP_ROOT}/backend"
VENV="${BACKEND}/.venv"

if [ ! -d "${BACKEND}" ]; then
  echo "ERROR: ${BACKEND} not found. Run git pull from ${APP_ROOT} first."
  exit 1
fi

pick_python() {
  for cmd in python3.11 python3.10 python3; do
    if command -v "${cmd}" >/dev/null 2>&1; then
      echo "${cmd}"
      return 0
    fi
  done
  echo "ERROR: python3 not found. Install Python 3.11 on EC2." >&2
  exit 1
}

if [ ! -f "${VENV}/bin/activate" ]; then
  PY="$(pick_python)"
  echo "Creating venv at ${VENV} using ${PY}..."
  "${PY}" -m venv "${VENV}"
fi

source "${VENV}/bin/activate"
pip install --upgrade pip -q
pip install -r "${BACKEND}/requirements.txt" -q
echo "venv OK: $(python --version) at ${VENV}"
