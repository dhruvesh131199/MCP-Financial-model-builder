# MCP Inspector (local dev only)

Official MCP testing UI for this project. **Not deployed to AWS EC2** — EC2 sparse checkout only pulls `backend/` and `deploy/`, so this folder never lands on the server.

Docs: [modelcontextprotocol.io/docs/tools/inspector](https://modelcontextprotocol.io/docs/tools/inspector)

## Prerequisites

- Node.js **22.7.5+** (for `npx @modelcontextprotocol/inspector`)
- MCP server running locally at `http://localhost:8080/mcp`

## Quick start

**Terminal 1 — app stack**

```bash
./scripts/dev.sh
```

**Terminal 2 — Inspector**

```bash
./scripts/inspect-mcp.sh
```

Open the URL printed in the terminal (usually `http://localhost:6274` with an auth token). Connect using the preloaded `financial-models` server config.

## Test `fetch_report` progress

1. **Tools** → `start_session` → Run → copy `session_id` from the response.
2. **Tools** → `fetch_report` with:
   - `report_type`: `"full_report"` (slow; best for progress) or `"just_financials"`
   - `tickers`: `["WMT"]`
   - `max_years`: `1`
   - `session_id`: paste UUID from step 1
3. Open **Notifications** (sidebar) while the tool runs — you should see `notifications/progress` and log lines like:
   - `Starting WMT FY2024 10-K ingest`
   - `Embedding WMT FY2024 sub-chunks (batch 1/N)`

## Inspector timeout settings (required for full 10-K)

In the Inspector UI → **Configuration**, set:

| Setting | Value |
|---------|--------|
| `MCP_SERVER_REQUEST_TIMEOUT` | `600000` (10 min) |
| `MCP_REQUEST_TIMEOUT_RESET_ON_PROGRESS` | `true` |
| `MCP_REQUEST_MAX_TOTAL_TIMEOUT` | `1200000` (20 min) |

Default `MCP_REQUEST_MAX_TOTAL_TIMEOUT` is **60 seconds** — too short for 10-K ingest + HF embed.

## CLI examples

List tools:

```bash
npx @modelcontextprotocol/inspector --cli http://localhost:8080/mcp \
  --transport http \
  --method tools/list
```

Call `start_session`:

```bash
npx @modelcontextprotocol/inspector --cli http://localhost:8080/mcp \
  --transport http \
  --method tools/call \
  --tool-name start_session
```

## vs Cursor

Use Inspector to verify server-side progress. Cursor may receive progress notifications but not show them in chat (known client limitation). Inspector **Notifications** pane is the source of truth for `fetch_report` step messages.

## AWS / production

Do **not** install or run Inspector on EC2. To test production MCP from your Mac, add a second entry in `mcp.json` (local only, do not commit secrets):

```json
"financial-models-prod": {
  "type": "streamable-http",
  "url": "https://myfmdc-mcp.duckdns.org/mcp"
}
```

Then: `npx @modelcontextprotocol/inspector --config devtools/mcp-inspector/mcp.json --server financial-models-prod`
