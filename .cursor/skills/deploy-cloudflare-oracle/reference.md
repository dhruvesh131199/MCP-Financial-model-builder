# Deploy reference — Cloudflare + Oracle

## systemd setup (on VM)

After `setup-vm.sh` and cloning repo:

```bash
cd /opt/financial-models/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install service units
sudo cp /opt/financial-models/deploy/oracle/financial-models-api.service /etc/systemd/system/
sudo cp /opt/financial-models/deploy/oracle/financial-models-mcp.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now financial-models-api financial-models-mcp
sudo systemctl status financial-models-api financial-models-mcp
```

Logs:

```bash
journalctl -u financial-models-api -f
journalctl -u financial-models-mcp -f
```

## Caddy

```bash
sudo cp /opt/financial-models/deploy/oracle/Caddyfile.example /etc/caddy/Caddyfile
# Edit domains, then:
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

If using Cloudflare proxy (orange cloud) with HTTP-01, set SSL mode to **Full** in Cloudflare → SSL/TLS.

## Oracle signup tips

1. Choose **home region** carefully — Always Free compute must stay in home region.
2. If ARM creation fails with "Out of host capacity":
   - Try a different availability domain
   - Try at off-peak hours
   - Some users succeed with `VM.Standard.E2.1.Micro` (1 GB) for testing only — **not recommended** for production API+MCP together
3. After 30-day trial: ensure only Always Free shapes remain; delete or downsize anything over limits.
4. Set billing alerts in Oracle Console even on free tier.

## Cloudflare Pages SPA routing

This app uses client-side routes (`/setup`, `/s/:id`). Add `frontend/public/_redirects`:

```
/*    /index.html   200
```

(Vite copies `public/` to `dist/` on build.)

## Env var matrix

| Where | Variable | Purpose |
|-------|----------|---------|
| Cloudflare Pages | `VITE_API_URL` | Dashboard polls this |
| Cloudflare Pages | `VITE_PUBLIC_MCP_URL` | Setup page copy-paste URL |
| Oracle `backend/.env` | `VIEW_BASE_URL` | Links returned by `start_session` |
| Oracle `backend/.env` | `MCP_HOST` | Bind address (0.0.0.0) |
| Oracle `backend/.env` | `MCP_PORT` | Internal MCP port (8080) |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Dashboard "Cannot reach API" | Check `VITE_API_URL`, Caddy api subdomain, `financial-models-api` service |
| Claude connector fails | MCP must be HTTPS; test `curl -I https://mcp.yourdomain.com/mcp` |
| MCP 406 on GET | Normal — means server is listening |
| Sessions lost after reboot | Data is on VM disk — ensure `backend/data/` persists and services restart |
| Caddy cert errors | Ports 80/443 open; DNS points to VM; Cloudflare SSL mode Full |

## Future improvements (not Phase 1)

- Docker Compose on VM for reproducible deploys
- R2 or block volume backup for `data/sessions/`
- Single process merging API + MCP behind one port
