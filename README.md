# Financial Model Builder (MCP)

MCP server + dashboard for building DCF models. Chat in **Cursor or Claude**; Python computes; each user gets a **private workspace link** (no signup).

**Phase 1:** HTTP MCP on localhost, anonymous sessions, manual DCF inputs.  
**Phase 2:** SEC EDGAR financials (`fetch_sec_financials`), Files sidebar, 1-hour session TTL.

## Architecture

```
Cursor  →  http://localhost:8080/mcp     (MCP tools)
Browser →  http://localhost:5173/s/{id}  (your dashboard)
Browser →  http://localhost:8000         (API reads session data)
```

Each user gets a random `session_id` (UUID). Data lives in `backend/data/sessions/{session_id}/`. Security = unguessable link (demo mode, no login).

## Quick start

```bash
chmod +x scripts/dev.sh
./scripts/dev.sh
```

This starts API (8000), MCP (8080), and frontend (5173).

### Cursor MCP config

**Option A — project config (already in this repo):** [`.cursor/mcp.json`](.cursor/mcp.json)

Cursor should pick this up when you open this project. If not, use Option B.

**Option B — global config:** Cursor **Settings → MCP → Add new MCP server**, or edit your user `mcp.json`:

```json
{
  "mcpServers": {
    "financial-models": {
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

Restart Cursor after adding. Check **Settings → MCP** — `financial-models` should be green (servers must be running first).

### Claude Desktop MCP config

1. Start the backend services first (`./scripts/dev.sh`).
2. Edit Claude's config file (macOS):

   `~/Library/Application Support/Claude/claude_desktop_config.json`

3. Add the block from [`claude_desktop_config.example.json`](claude_desktop_config.example.json) in this repo (merge into existing `mcpServers` if you already have other servers).
4. **Fully quit** Claude Desktop (Cmd+Q) and reopen — not just close the window.
5. Look for the tools icon in chat; you should see `start_session`, `set_model_inputs`, `run_dcf`, `resolve_ticker`, and `fetch_sec_financials`.


### Try it

In Cursor or Claude:

> I want to build a DCF.

The host should call `start_session` (you get a dashboard link), ask for assumptions, call `set_model_inputs` with only what you stated, then `run_dcf` when `ready=true`.

Example after you provide numbers:

> Revenue $100M, 10% growth for 5 years, EBITDA margin 25%, tax 21%, CapEx 3%, NWC 2%, WACC 10%, terminal growth 2%.

The model appears on your dashboard within a few seconds.

### SEC financials

> Fetch Apple SEC financial reports.

or, for more history:

> Pull Tesla financials for the last 5 years — annual and quarterly.

The host calls `fetch_sec_financials`; reports appear in the **Files** sidebar on your dashboard. Repeat requests with the same scope do not create duplicate entries. Session data is deleted after one hour (`SESSION_TTL_SECONDS`, default 3600).

## Manual start (3 terminals)

```bash
# Terminal 1 — API
cd backend && source .venv/bin/activate && uvicorn api.main:app --reload --port 8000

# Terminal 2 — MCP
cd backend && source .venv/bin/activate && python mcp/server.py

# Terminal 3 — Frontend
cd frontend && npm run dev
```

## Environment

Copy `backend/.env.example` to `backend/.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `VIEW_BASE_URL` | `http://localhost:5173` | Base URL for dashboard links in tool responses |
| `MCP_HOST` | `0.0.0.0` | MCP server bind address |
| `MCP_PORT` | `8080` | MCP server port |

## Deploy (production)

**Live app:** https://mcp-financial-model-builder.onrender.com · **Setup:** [/setup](https://mcp-financial-model-builder.onrender.com/setup)

| Piece | Host | Auto-deploy on `git push`? |
|-------|------|----------------------------|
| Frontend (React) | [Render](https://render.com) — `render.yaml` | **Yes** |
| API + MCP | AWS EC2 — **[DEPLOY.md](DEPLOY.md)** · **[deploy/aws/README.md](deploy/aws/README.md)** | **No** — run `deploy/aws/update-ec2.sh` on server |

Local dev: `./scripts/dev.sh` (see Quick start below).

### Legacy / alternatives

Swap `localhost` for public domains when deployed:

| Local | Deployed |
|-------|----------|
| `http://localhost:8080/mcp` | `https://mcp.yourdomain.com/mcp` |
| `http://localhost:8000` | `https://api.yourdomain.com` |
| `http://localhost:5173/s/{id}` | `https://your-app.onrender.com/s/{id}` |

Set `VIEW_BASE_URL` on the MCP server to your Render app URL.

## Tests

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ -v
```

## Project docs

- [deploy/aws/README.md](deploy/aws/README.md) — production EC2 + Render guide
- [PLAN.md](PLAN.md) — living plan
- [KEY_LEARNINGS_AND_CHALLENGES.md](KEY_LEARNINGS_AND_CHALLENGES.md) — decisions & interview notes
