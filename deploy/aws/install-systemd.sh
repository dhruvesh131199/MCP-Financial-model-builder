#!/usr/bin/env bash
# Install systemd units for API + MCP on Amazon Linux (ec2-user, ~/financial-models).
# Usage on EC2: bash ~/financial-models/deploy/aws/install-systemd.sh
set -euo pipefail

APP_ROOT="${HOME}/financial-models"
BACKEND="${APP_ROOT}/backend"

if [ ! -f "${BACKEND}/.env" ]; then
  echo "ERROR: ${BACKEND}/.env missing. Copy .env.example and set VIEW_BASE_URL."
  exit 1
fi

sudo tee /etc/systemd/system/financial-models-api.service > /dev/null <<EOF
[Unit]
Description=Financial Model Builder API
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=${BACKEND}
EnvironmentFile=${BACKEND}/.env
ExecStart=${BACKEND}/.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/financial-models-mcp.service > /dev/null <<EOF
[Unit]
Description=Financial Model Builder MCP
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=${BACKEND}
EnvironmentFile=${BACKEND}/.env
ExecStart=${BACKEND}/.venv/bin/python mcp/server.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now financial-models-api financial-models-mcp

echo ""
sudo systemctl --no-pager status financial-models-api financial-models-mcp || true
