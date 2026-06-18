# AWS EC2 backend

**Start here:** [README.md](README.md) — full explanation, SSH from Mac, starting servers, troubleshooting.

Quick reference:

- **SSH:** `ssh -i ~/Downloads/your-key.pem ec2-user@YOUR_PUBLIC_IP`
- **API + MCP:** manual uvicorn + `python mcp/server.py`, or `bash deploy/aws/install-systemd.sh`
- **HTTPS:** Caddy + DuckDNS (see `Caddyfile.example`)
- **Frontend:** Render static site — not on EC2
