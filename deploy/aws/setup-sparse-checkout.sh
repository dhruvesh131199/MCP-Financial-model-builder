#!/usr/bin/env bash
# Alias — use ensure-sparse-checkout.sh (called automatically by update-ec2.sh).
exec "$(dirname "$0")/ensure-sparse-checkout.sh"
