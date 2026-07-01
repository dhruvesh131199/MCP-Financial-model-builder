# Production deploy: Render (frontend) + AWS EC2 (backend)

Plain-English guide for what we set up and how to run it day to day.

## What we built (the whole picture)

You did **not** upload a zip file to AWS. You:

1. **Cloned this GitHub repo** onto a small AWS server (EC2).
2. **Ran two Python programs** on that server:
   - **API** (port 8000) — the dashboard asks this for model data.
   - **MCP** (port 8080) — Claude/Cursor call tools like `start_session` and `run_dcf`.
3. **Installed Caddy** — adds free HTTPS (`https://`) in front of those two programs.
4. **Pointed DuckDNS** at the server so the internet can find it by name.
5. **Deployed the React app on Render** — static site only; it talks to your API over HTTPS.

```
  Stranger's browser                    Your EC2 (Amazon Linux)
  ─────────────────                     ─────────────────────────
  Render CDN                            ┌─ Caddy :443 (HTTPS)
  https://your-app.onrender.com         │     ├─► API  :8000  (FastAPI)
       │                                │     └─► MCP  :8080  (MCP server)
       │  polls API                     └─ session files on disk
       └──────────────────────────────► https://myfmdc-api.duckdns.org

  Claude Desktop
       │
       └──────────────────────────────► https://myfmdc-mcp.duckdns.org/mcp
```

| Piece | Where it lives | What it does |
|-------|----------------|--------------|
| **Dashboard UI** | Render | React app — `/setup`, `/s/{session-id}` |
| **API** | EC2 :8000 | Returns session/model JSON |
| **MCP** | EC2 :8080 | Tools for Claude |
| **Caddy** | EC2 :443 | HTTPS certificates + reverse proxy |
| **DuckDNS** | duckdns.org | Free names → your EC2 public IP |
| **Your Mac** | local | SSH to manage EC2; optional local dev with `./scripts/dev.sh` |

---

## URLs (fill in yours)

| Role | Example (this project) |
|------|-------------------------|
| Frontend | `https://mcp-financial-model-builder.onrender.com` |
| API | `https://myfmdc-api.duckdns.org` |
| MCP | `https://myfmdc-mcp.duckdns.org/mcp` |
| EC2 public IP | From AWS console → Instances → Public IPv4 |

**DuckDNS:** both subdomains must use the **public** IP (from `curl -s http://checkip.amazonaws.com` on EC2), not the private `172.31.x.x` address.

---

## One-time setup (already done if you followed deploy)

- [ ] EC2 instance (Amazon Linux 2023, `ec2-user`)
- [ ] Security group: inbound **22, 80, 443**
- [ ] Python **3.11** venv at `~/financial-models/backend/.venv`
- [ ] `backend/.env` with `VIEW_BASE_URL` = your Render URL
- [ ] Caddy installed + `/etc/caddy/Caddyfile` (see `Caddyfile.example`)
- [ ] Render static site + `VITE_API_URL` + `VITE_PUBLIC_MCP_URL`

### Why Python 3.11?

Amazon Linux ships Python 3.9. The `mcp` package needs **3.10+**. Always use the venv:

```bash
source ~/financial-models/backend/.venv/bin/activate
```

### `backend/.env` on EC2

```env
VIEW_BASE_URL=https://YOUR-APP.onrender.com
MCP_HOST=0.0.0.0
MCP_PORT=8080
SEC_USER_AGENT=YourAppName you@yourdomain.com
SESSION_TTL_SECONDS=3600
```

`VIEW_BASE_URL` is the link Claude returns from `start_session`. Must match Render exactly (no trailing slash).

`SEC_USER_AGENT` is required by SEC EDGAR (descriptive app name + contact email) for `fetch_report`.

`SESSION_TTL_SECONDS=3600` deletes each anonymous session folder after one hour — no long-lived user data on disk.

---

## From your Mac — SSH into EC2

Replace paths and IP with yours.

```bash
# First time only — lock down key permissions
chmod 400 ~/Downloads/your-key.pem

# Connect
ssh -i ~/Downloads/your-key.pem ec2-user@YOUR_PUBLIC_IP
```

**New Terminal tab** = second SSH session (`Cmd+T`, run the same `ssh` command again).

### EC2 was stopped?

1. AWS Console → EC2 → Instances → **Start instance**
2. If you have no **Elastic IP**, the **public IP may change** → update DuckDNS to the new IP
3. SSH in and start the servers again (below)

---

## Start the servers on EC2

Caddy should auto-start via systemd. **API and MCP** must be running too or HTTPS will error.

### Option A — Manual (what you did first) — 2 SSH tabs

**Tab 1 — API**

```bash
source ~/financial-models/backend/.venv/bin/activate
cd ~/financial-models/backend
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Leave running. Open **Tab 2**.

**Tab 2 — MCP**

```bash
source ~/financial-models/backend/.venv/bin/activate
cd ~/financial-models/backend
python mcp/server.py
```

Leave running.

**Check on EC2 (Tab 3 or background):**

```bash
curl -s http://127.0.0.1:8000/health          # → {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/mcp   # → 406 is OK
curl -s https://myfmdc-api.duckdns.org/health   # → {"status":"ok"} from internet
```

### Option B — systemd (runs after reboot, no extra tabs)

One-time install on EC2:

```bash
bash ~/financial-models/deploy/aws/install-systemd.sh
```

Then daily:

```bash
sudo systemctl start financial-models-api financial-models-mcp
# Caddy already: sudo systemctl start caddy
```

Status:

```bash
sudo systemctl status financial-models-api financial-models-mcp caddy
```

Logs:

```bash
journalctl -u financial-models-api -n 30 --no-pager
journalctl -u financial-models-mcp -n 30 --no-pager
journalctl -u caddy -n 30 --no-pager
```

### Caddy only

```bash
sudo systemctl status caddy
sudo systemctl restart caddy
```

---

## Render (frontend)

Connect repo via Blueprint (`render.yaml` at repo root) or manual static site:

| Setting | Value |
|---------|--------|
| Root directory | `frontend` |
| Build | `npm ci && npm run build` |
| Publish | `dist` |

**Environment variables** (Production):

| Variable | Value |
|----------|--------|
| `VITE_API_URL` | `https://myfmdc-api.duckdns.org` |
| `VITE_PUBLIC_MCP_URL` | `https://myfmdc-mcp.duckdns.org/mcp` |

Change env → **Manual Deploy** (Vite bakes them at build time).

---

## Claude setup (for strangers)

See `/setup` on your Render URL. Short version:

1. Claude → Settings → Connectors → add `https://myfmdc-mcp.duckdns.org/mcp`
2. Restart Claude (`Cmd+Q`)
3. New chat → **+** → **Connectors** → **Financial Models**
4. Ask: *Call start_session and give me my dashboard link.*

---

## Local dev on your Mac (unchanged)

For hacking on your laptop — no EC2 needed:

```bash
./scripts/dev.sh
```

- Dashboard: http://localhost:5173  
- API: http://localhost:8000  
- MCP: http://localhost:8080/mcp  

---

## Auto-deploy on git push?

| Host | Auto-deploy? |
|------|----------------|
| **Render** (frontend) | **Yes** — push to `main` triggers a new build (if GitHub auto-deploy is enabled in Render dashboard). |
| **EC2** (API + MCP) | **No** — run `bash ~/financial-models/deploy/aws/update-ec2.sh` after SSH in. |

See **[DEPLOY.md](../../DEPLOY.md)** at repo root for the big picture.

## Pull code updates on EC2

```bash
bash ~/financial-models/deploy/aws/update-ec2.sh
```

Or manually:

```bash
cd ~/financial-models
git pull
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
sudo systemctl restart financial-models-api financial-models-mcp
```

---

## Troubleshooting

| Symptom | Likely fix |
|---------|------------|
| `curl 127.0.0.1:8000` fails | Start API (uvicorn) |
| `curl 127.0.0.1:8000` OK but `https://myfmdc-api…` times out | DuckDNS IP wrong; security group missing **443**; Caddy down — run `bash deploy/aws/diagnose-ec2.sh` |
| Claude fetch works but dashboard empty | API unreachable from browser — fix HTTPS above (MCP and API are separate URLs) |
| Microsoft/Google “server error” after Apple OK | SEC fetch is slow (~15s/company); EC2 may OOM or Claude times out — fetch **one ticker per call**, try `include_quarterly=false` |
| MCP curl fails | Start `python mcp/server.py` |
| HTTPS fails, local OK | DuckDNS wrong IP; security group missing 80/443 |
| Caddy errors | `sudo journalctl -u caddy -n 50 -l` |
| Dashboard can't load models | `VIEW_BASE_URL` on EC2 must match Render URL |
| `pip install mcp` fails | Use Python 3.11 venv, not system 3.9 |
| EC2 rebooted | Restart API + MCP; update DuckDNS if IP changed |

**Get public IP on EC2:**

```bash
curl -s http://checkip.amazonaws.com
```

---

## Cost note

- **Render static site:** free tier
- **EC2 t2/t3.micro:** free 12 months, then ~$8–10/mo if left running
- **DuckDNS:** free

---

## Files in this folder

| File | Purpose |
|------|---------|
| `README.md` | This guide |
| `Caddyfile.example` | HTTPS config template |
| `install-systemd.sh` | One-time: API + MCP run in background |
| `update-ec2.sh` | After `git push`: pull + restart on EC2 |
| `diagnose-ec2.sh` | Local + HTTPS troubleshooting on the VM |

Oracle deploy (alternative backend): `deploy/oracle/`
