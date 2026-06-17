#!/usr/bin/env bash
# Bootstrap Oracle Always Free VM for Financial Model Builder backend.
# Run as root: sudo bash setup-vm.sh
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y \
  python3 python3-venv python3-pip \
  git curl ca-certificates \
  debian-keyring debian-archive-keyring apt-transport-https

# Caddy
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt-get update
apt-get install -y caddy

mkdir -p /opt/financial-models
echo "VM ready. Clone repo to /opt/financial-models, configure .env, install systemd units, copy Caddyfile."
