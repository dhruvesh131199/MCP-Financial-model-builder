---
name: deploy-cloudflare-oracle
description: >-
  Deploy MCP Financial Model Builder: static React frontend on Cloudflare Pages,
  Python API + MCP on Oracle Cloud Always Free VM. Use when the user asks to deploy,
  host, go live, production URLs, Oracle Cloud, Cloudflare Pages, or set up public
  HTTPS for strangers.
---

# Deploy: Cloudflare Pages + Oracle Always Free

## Architecture

```
Browser  →  https://app.yourdomain.com          (Cloudflare Pages — static Vite build)
Browser  →  https://app.yourdomain.com/s/{id}   (same; dashboard polls API)
Browser  →  https://api.yourdomain.com          (Oracle VM — FastAPI :8000)
Claude   →  https://mcp.yourdomain.com/mcp      (Oracle VM — MCP :8080)
```

One Oracle **Always Free** ARM VM runs API + MCP + Caddy (TLS). Session files live on disk at `backend/data/sessions/`.

## Is it really free?

**Cloudflare Pages (frontend):** Yes — $0 for static hosting. Unlimited bandwidth for static assets; 500 builds/month on free plan. See [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/).

**Oracle Always Free (backend):** Yes — **Always Free resources stay $0 for the life of the account** if you stay within limits. Official docs: [Oracle Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).

| Resource | Always Free limit (typical) |
|----------|----------------------------|
| ARM VM (Ampere A1) | 2 OCPU, 12 GB RAM total |
| AMD micro VM | Up to 2× VM.Standard.E2.1.Micro (1 GB each — too small for API+MCP) |
| Block storage | 200 GB |
| Outbound data | 10 TB/month |

**Honest caveats (not hidden costs, but friction):**

- Credit card required at Oracle signup (identity verification; you are not charged if you only use Always Free shapes).
- $300 trial credits for 30 days — **do not** provision paid shapes or you may be charged after trial.
- ARM instances are often **"Out of capacity"** in popular regions — retry other availability domains or regions.
- Oracle may **reclaim idle** Always Free Ampere instances if CPU, network, and memory are all below 20% for 7 days (light traffic demo is usually fine).
- Signup approval is not guaranteed in all countries.

**Recommendation for this project:** 1× `VM.Standard.A1.Flex` with **2 OCPU, 12 GB RAM** in home region. Enough for API + MCP + Caddy with headroom.

## Agent checklist

Copy and track:

```
Deploy progress:
- [ ] Domain on Cloudflare (DNS)
- [ ] Oracle VM created (Always Free ARM, Ubuntu 22.04)
- [ ] Firewall: 22, 80, 443 open
- [ ] deploy/oracle/setup-vm.sh run on VM
- [ ] Repo cloned, backend/.env set
- [ ] systemd services enabled (api + mcp)
- [ ] Caddy serving api + mcp subdomains
- [ ] Cloudflare Pages project connected
- [ ] VITE_* env vars set on Pages
- [ ] VITE_PUBLIC_MCP_URL updated in frontend config
- [ ] End-to-end: start_session from Claude → dashboard loads
```

## Phase 1 — Oracle VM (backend)

### 1. Create VM

Oracle Console → Compute → Instances → Create:

- **Shape:** VM.Standard.A1.Flex — **2 OCPU, 12 GB** (Always Free-eligible label must show)
- **Image:** Ubuntu 22.04 or 24.04
- **Boot volume:** 50 GB (within 200 GB free block storage)
- **Networking:** assign public IPv4
- **SSH key:** upload your public key

Security list / NSG — ingress:

- TCP 22 (SSH, restrict to your IP if possible)
- TCP 80, 443 (Caddy + Let's Encrypt)

### 2. Bootstrap VM

From your laptop (replace IP and domain):

```bash
scp -r deploy/oracle ubuntu@YOUR_VM_IP:~/
ssh ubuntu@YOUR_VM_IP
sudo bash ~/oracle/setup-vm.sh
```

Then clone the repo and configure:

```bash
sudo mkdir -p /opt/financial-models
sudo chown ubuntu:ubuntu /opt/financial-models
git clone YOUR_REPO_URL /opt/financial-models
cd /opt/financial-models/backend
cp .env.example .env
```

Edit `/opt/financial-models/backend/.env`:

```env
VIEW_BASE_URL=https://app.yourdomain.com
MCP_HOST=0.0.0.0
MCP_PORT=8080
```

Install Python deps and enable services — see [reference.md](reference.md) § systemd.

### 3. Caddy + DNS

Copy `deploy/oracle/Caddyfile.example` → `/etc/caddy/Caddyfile`. Replace `yourdomain.com` with real domain.

Cloudflare DNS (proxy **orange cloud ON** for DDoS; Caddy gets certs via HTTP-01 or use Cloudflare DNS challenge — default example uses HTTP-01 on 80/443):

| Type | Name | Content |
|------|------|---------|
| A | api | VM public IP |
| A | mcp | VM public IP |

Reload: `sudo systemctl reload caddy`

Verify:

```bash
curl -s https://api.yourdomain.com/health
curl -s -o /dev/null -w "%{http_code}" https://mcp.yourdomain.com/mcp
# MCP may return 406 on GET — that means it's up
```

## Phase 2 — Cloudflare Pages (frontend)

### 1. Connect repo

Cloudflare Dashboard → Workers & Pages → Create → Pages → Connect Git.

| Setting | Value |
|---------|-------|
| Root directory | `frontend` |
| Build command | `npm ci && npm run build` |
| Build output | `dist` |

### 2. Environment variables (Production)

| Variable | Example |
|----------|---------|
| `VITE_API_URL` | `https://api.yourdomain.com` |
| `VITE_PUBLIC_MCP_URL` | `https://mcp.yourdomain.com/mcp` |

Redeploy after changing env vars (Vite bakes them at build time).

### 3. Custom domain

Pages → Custom domains → add `app.yourdomain.com`. Cloudflare creates DNS automatically if the zone is on Cloudflare.

Update setup page URL constant if not using env: `frontend/src/config/publicUrls.ts`.

## Phase 3 — Smoke test

1. Open `https://app.yourdomain.com/setup` — MCP URL shows production HTTPS link.
2. In Claude: Settings → Connectors → add `https://mcp.yourdomain.com/mcp`, restart, enable **Financial Models** in chat.
3. Ask Claude to call `start_session` — open the `view_url` (should be `https://app.yourdomain.com/s/...`).
4. Run a DCF — dashboard should poll API and show the model within seconds.

## Files in this repo

| Path | Purpose |
|------|---------|
| `deploy/oracle/setup-vm.sh` | Install Python, Caddy, create dirs |
| `deploy/oracle/Caddyfile.example` | TLS reverse proxy for api + mcp |
| `deploy/oracle/financial-models-api.service` | systemd unit for uvicorn |
| `deploy/oracle/financial-models-mcp.service` | systemd unit for MCP server |

Detailed commands and troubleshooting: [reference.md](reference.md).

## Do not use for backend

Render/Railway/Cloud Run free tiers — cold starts (~30–60s) break MCP for strangers. Oracle VM stays on 24/7 with no spin-up delay.
