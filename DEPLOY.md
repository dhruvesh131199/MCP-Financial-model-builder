# Production deploy — start here

You survived. This is the map of what’s live and how updates work.

## What’s running where

```
┌─────────────────────────────────────────────────────────────────┐
│  RENDER (auto-deploys on git push)                              │
│  https://financial-model-dashboard.onrender.com                 │
│  React dashboard + /setup page                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ polls API
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  AWS EC2 (you update manually)                                  │
│  https://myfmdc-api.duckdns.org      → API  (:8000)             │
│  https://myfmdc-mcp.duckdns.org/mcp  → MCP  (:8080)             │
│  Caddy on :443 · systemd keeps services running                 │
└─────────────────────────────────────────────────────────────────┘
                            ▲
                            │ Custom Connector
┌───────────────────────────┴─────────────────────────────────────┐
│  Claude Desktop (user’s Mac)                                    │
└─────────────────────────────────────────────────────────────────┘
```

| URL | What |
|-----|------|
| https://financial-model-dashboard.onrender.com | Dashboard + setup UI |
| https://financial-model-dashboard.onrender.com/setup | Claude setup instructions |
| https://myfmdc-api.duckdns.org | Backend API |
| https://myfmdc-mcp.duckdns.org/mcp | MCP for Claude |

## Does it auto-deploy on every commit?

| Host | Auto-deploy? | How |
|------|--------------|-----|
| **Render** (frontend) | **Yes** — if GitHub auto-deploy is on (default) | Push to `main` → Render builds `frontend/` → live in ~2 min |
| **EC2** (API + MCP) | **No** | SSH in → `bash deploy/aws/update-ec2.sh` (or `git pull` + restart services) |

Render only rebuilds the **static site**. Python on EC2 does **not** know about GitHub until you pull.

### After you push code

**Frontend only changed** → do nothing; Render handles it.

**Backend changed** (`backend/`) → on EC2:

```bash
ssh -i ~/Downloads/your-key.pem ec2-user@YOUR_PUBLIC_IP
bash ~/financial-models/deploy/aws/update-ec2.sh
```

**First time only** — if the EC2 clone still has `frontend/`, drop it and use sparse checkout:

```bash
bash ~/financial-models/deploy/aws/setup-sparse-checkout.sh
```

After that, `update-ec2.sh` only pulls backend + deploy files.

## EC2 `.env` (copy on server)

```env
VIEW_BASE_URL=https://financial-model-dashboard.onrender.com
MCP_HOST=0.0.0.0
MCP_PORT=8080
```

## Render env vars

| Variable | Value |
|----------|--------|
| `VITE_APP_URL` | `https://financial-model-dashboard.onrender.com` |
| `VITE_API_URL` | `https://myfmdc-api.duckdns.org` |
| `VITE_PUBLIC_MCP_URL` | `https://myfmdc-mcp.duckdns.org/mcp` |

**CORS rule:** `VIEW_BASE_URL` on EC2 must **exactly match** `VITE_APP_URL` on Render (same URL in the browser address bar).

Change these → **Manual Deploy** on Render.

## Health checks

```bash
# API
curl -s https://myfmdc-api.duckdns.org/health

# MCP (406 = good)
curl -s -o /dev/null -w "%{http_code}\n" https://myfmdc-mcp.duckdns.org/mcp
```

## Full runbook

Detailed SSH, systemd, DuckDNS, Caddy, troubleshooting:

**[deploy/aws/README.md](deploy/aws/README.md)**

## Local dev (your Mac)

No EC2 needed:

```bash
./scripts/dev.sh
```
