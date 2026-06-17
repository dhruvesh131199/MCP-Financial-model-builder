# Deploy reference — Render + Oracle

## Oracle VM — full bootstrap

```bash
# From your Mac (replace IP)
scp -r deploy/oracle ubuntu@YOUR_VM_IP:~/
ssh ubuntu@YOUR_VM_IP
sudo bash ~/oracle/setup-vm.sh

sudo mkdir -p /opt/financial-models
sudo chown ubuntu:ubuntu /opt/financial-models
git clone https://github.com/dhruvesh131199/MCP-Financial-model-builder.git /opt/financial-models

cd /opt/financial-models/backend
cp .env.example .env
# Edit .env — set VIEW_BASE_URL to your Render URL

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

sudo cp /opt/financial-models/deploy/oracle/financial-models-api.service /etc/systemd/system/
sudo cp /opt/financial-models/deploy/oracle/financial-models-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now financial-models-api financial-models-mcp

sudo cp /opt/financial-models/deploy/oracle/Caddyfile.example /etc/caddy/Caddyfile
# Edit yourdomain.com → real domain
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

## DNS (api + mcp only)

Point at Oracle VM public IP (Cloudflare, Namecheap, etc.):

| Type | Name | Value |
|------|------|-------|
| A | api | VM IP |
| A | mcp | VM IP |

Frontend lives on Render — **no** A record needed for app unless using custom domain on Render.

## Render static site notes

- **No cold start** — files served from CDN edge.
- Free tier: 100 GB bandwidth/month (enough for demo).
- `VITE_*` vars are baked at **build** time — change env → trigger **Manual Deploy**.
- SPA routing: `render.yaml` includes rewrite `/* → /index.html`, or set in dashboard.

## Env var matrix

| Where | Variable | Purpose |
|-------|----------|---------|
| Render | `VITE_API_URL` | Dashboard API base |
| Render | `VITE_PUBLIC_MCP_URL` | Setup page connector URL |
| Oracle `.env` | `VIEW_BASE_URL` | Links from `start_session` (Render app URL) |
| Oracle `.env` | `MCP_HOST` / `MCP_PORT` | MCP bind |

## CORS

API allows `VIEW_BASE_URL` plus localhost. Set `VIEW_BASE_URL` to exact Render URL (no trailing slash):

```env
VIEW_BASE_URL=https://financial-model-dashboard.onrender.com
```

Optional extra origins: `CORS_ORIGINS=https://app.yourdomain.com`

## Domain-minimal path (no purchase)

| Service | URL |
|---------|-----|
| Frontend | `https://your-app.onrender.com` (free from Render) |
| API | `https://api.yourname.duckdns.org` (DuckDNS + Caddy on Oracle) |
| MCP | `https://mcp.yourname.duckdns.org` |

Update Caddyfile and DuckDNS A records to VM IP.

## Oracle signup

1. [oracle.com/cloud/free](https://www.oracle.com/cloud/free/) → sign up
2. Pick home region (permanent)
3. Wait for approval email
4. Create A1 Flex instance — retry if out of capacity

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Dashboard CORS error | `VIEW_BASE_URL` must match Render URL exactly |
| Render 404 on `/setup` | Add SPA rewrite rule |
| MCP fails in Claude | Must be HTTPS; test with curl |
| Render build missing env | Redeploy after setting `VITE_*` |
