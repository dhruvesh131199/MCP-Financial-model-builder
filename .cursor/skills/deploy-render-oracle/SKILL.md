---
name: deploy-render-oracle
description: >-
  Deploy MCP Financial Model Builder: static React frontend on Render Static Site,
  Python API + MCP on Oracle Cloud Always Free VM. Use when the user asks to deploy,
  host, go live, Render, Oracle Cloud, production URLs, or public HTTPS for strangers.
---

# Deploy: Render Static Site + Oracle Always Free

## Architecture

```
Browser  →  https://YOUR-APP.onrender.com        (Render — static Vite build, no cold start)
         or https://app.yourdomain.com           (optional custom domain on Render)
Browser  →  …/s/{id}                             (dashboard polls API)
Browser  →  https://api.yourdomain.com          (Oracle VM — FastAPI :8000)
Claude   →  https://mcp.yourdomain.com/mcp      (Oracle VM — MCP :8080)
```

**Why this split:** Render **static sites** are always-on CDN — no 1-minute wake-up. Render **web services** sleep on free tier — do **not** use Render for API/MCP. Oracle VM stays on 24/7 for backend.

## Is it free?

| Piece | Host | Cost | Cold start? |
|-------|------|------|-------------|
| Frontend | Render Static Site | $0 | No — instant |
| API + MCP | Oracle Always Free ARM VM | $0 (within limits) | No — always on |
| Domain | Optional | ~$10/yr or use `*.onrender.com` for app only | — |

Oracle caveats: credit card for signup, ARM capacity often full, idle reclaim after 7 days. See [reference.md](reference.md).

**Backend still needs a domain** (or DuckDNS) for `api.*` and `mcp.*` HTTPS — Claude requires HTTPS for connectors. Frontend can use free `something.onrender.com` without buying a domain.

## Agent checklist

```
Deploy progress:
- [ ] Oracle account approved
- [ ] Oracle VM (A1 Flex 2 OCPU / 12 GB)
- [ ] VM bootstrapped (setup-vm.sh, systemd, Caddy)
- [ ] DNS: api + mcp → VM IP
- [ ] backend/.env VIEW_BASE_URL = Render app URL
- [ ] Render Static Site connected to GitHub
- [ ] Render env: VITE_API_URL, VITE_PUBLIC_MCP_URL
- [ ] Smoke test: Claude start_session → dashboard on Render
```

## Phase 1 — Oracle VM (backend)

Same as before — see [reference.md](reference.md) for full commands.

1. Create **VM.Standard.A1.Flex** (2 OCPU, 12 GB), Ubuntu, ports 22/80/443.
2. Run `deploy/oracle/setup-vm.sh`, clone repo, `backend/.env`:

```env
VIEW_BASE_URL=https://YOUR-APP.onrender.com
MCP_HOST=0.0.0.0
MCP_PORT=8080
```

3. Enable systemd services + Caddy (`api.yourdomain.com`, `mcp.yourdomain.com`).

Verify:

```bash
curl -s https://api.yourdomain.com/health
curl -s -o /dev/null -w "%{http_code}" https://mcp.yourdomain.com/mcp
```

## Phase 2 — Render Static Site (frontend)

### Option A — Blueprint (repo has `render.yaml`)

1. Push repo to GitHub (includes `render.yaml`).
2. [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint** → connect repo.
3. Set environment variables when prompted (or after deploy):

| Variable | Example |
|----------|---------|
| `VITE_API_URL` | `https://api.yourdomain.com` |
| `VITE_PUBLIC_MCP_URL` | `https://mcp.yourdomain.com/mcp` |

4. Deploy. Note your URL: `https://financial-model-dashboard.onrender.com` (name may vary).

5. Update Oracle `VIEW_BASE_URL` to match the Render URL if you set it before Render existed.

### Option B — Manual static site

Render → **New** → **Static Site** → connect GitHub:

| Setting | Value |
|---------|-------|
| Root directory | `frontend` |
| Build command | `npm ci && npm run build` |
| Publish directory | `dist` |

Add **Rewrite rule** (Render dashboard → Redirects/Rewrites):

| Source | Destination |
|--------|-------------|
| `/*` | `/index.html` |

Set the same `VITE_*` env vars → **Manual Deploy**.

### Custom domain (optional)

Render site → **Settings** → **Custom Domains** → add `app.yourdomain.com`. Update `VIEW_BASE_URL` on Oracle to match.

## Phase 3 — Smoke test

1. `https://YOUR-APP.onrender.com/setup` — shows production MCP URL.
2. Claude → Connectors → `https://mcp.yourdomain.com/mcp` → restart → **+ → Connectors → Financial Models**.
3. `start_session` → open `view_url` (Render URL) → run a DCF → dashboard updates.

## Repo deploy files

| Path | Purpose |
|------|---------|
| `render.yaml` | Render Blueprint for static frontend |
| `deploy/oracle/*` | VM bootstrap, Caddy, systemd |

## Do not use

- **Render Web Service** for API/MCP (free tier sleeps ~1 min)
- **Cloudflare Pages** — superseded by Render for this project unless user switches back
