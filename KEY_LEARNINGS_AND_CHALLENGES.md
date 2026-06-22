# Key Learnings & Challenges

Living document for interview prep and project retrospectives.  
**Update this file when a major decision, mistake, or lesson happens** — not for every small bugfix.

---

## Project in one sentence

MCP server + dashboard where Cursor/Claude **orchestrates** (asks questions, calls tools) and Python **computes** (DCF math) — rebuilt from a prior REST+Groq prototype, starting with one manual-input DCF tool.

---

## Prior project context

This is a **fresh MCP-first rewrite** of ideas proven in `AI assisted Financial model builder` (REST API + Groq + embedded chat). That project validated DCF math, SEC ingest, and dashboard UX. This project drops Groq and embedded chat — the user's host (Cursor/Claude) is the orchestrator.

---

## Major design decisions (Phase 1)

| Decision | Choice | Options considered | Why this choice |
|----------|--------|-------------------|-----------------|
| Orchestrator | **Cursor/Claude via MCP** | Keep Groq in backend; regex routing | User chats where they already work; no API key for our LLM; simpler backend |
| Phase 1 scope | **One tool, all manual inputs** | Multi-tool bundle flow; SEC auto-fetch day one | Prove MCP → engine → dashboard loop before adding complexity |
| Who does math? | **Python engine only** | LLM computes in chat | Non-negotiable for trust in financial models |
| MCP transport | **HTTP streamable** (`localhost:8080/mcp`) | stdio subprocess | Matches deploy model from day one; strangers use URL in Cursor config |
| User identity | **Random UUID session** — folder per user | Login/signup; shared latest_model | Demo-friendly; no auth friction; unguessable link = isolation |
| Frontend (Phase 1) | **Single page, poll API** | Full 20/80 sidebar; WebSocket | See model in action fast; sidebar comes Phase 3 |
| Codebase | **Fresh start** | Port entire REST project | Clean MCP architecture; reference sibling for algorithms only |

---

## Chronological journey

### 2026-06-17 — Project kickoff & planning

- Empty workspace; sibling REST project has working DCF, SEC, variable bundles.
- **Decision:** Start with one `run_dcf` tool, not four tools (`prepare_model_inputs`, etc.) — walk before running.
- **Decision:** All manual inputs in Phase 1 — SEC auto-fill deferred to Phase 2.
- **Decision:** Local MCP first, but structure for Render/GCP deploy (stdio vs HTTP via env var).
- **Rejected:** Bulk-copy REST codebase — fresh layout with MCP as first-class entry point.
- **Rejected:** Zoom MCP as template — not relevant; use FastMCP directly.

---

## Technical challenges worth mentioning in interviews

1. **Two-process architecture** — MCP (spawned by Cursor) and FastAPI (dev server) don't share memory. Solution: file-based store with `updated_at` for frontend polling.
2. **Trust boundary** — DCF engine validates WACC > terminal g, growth list length, percent normalization (10 vs 0.10). Host must never do arithmetic.
3. **Deploy path without rewrite** — Same `run_dcf` handler; only transport layer changes (stdio → HTTP) when moving to Render/GCP.
4. **Phased product thinking** — Prior REST project proved value of phases (chat → DCF → SEC). This project applies same discipline to MCP migration.

---

## Stack (Phase 1)

| Layer | Tech |
|-------|------|
| MCP | Python, FastMCP, stdio (local) / streamable-http (deploy) |
| Engine | Pydantic, pure Python DCF |
| API | FastAPI, CORS for Vite |
| Frontend | React, Vite, TypeScript, Tailwind |
| Store | JSON file (`backend/data/latest_model.json`) |

---

## What I would say in an interview (30-second version)

> "I'm rebuilding my financial model builder as an MCP server so users integrate one tool in Cursor or Claude instead of a custom chat UI. Phase one is deliberately minimal — one DCF tool, manual inputs, Python does all math, and a React dashboard polls for results. I architected it so local dev uses stdio MCP but the same code deploys to Render or GCP over HTTP. I learned from my first version that phasing matters: prove the loop before adding SEC auto-fetch and session management."

---

## Maintenance log

Newest first. Add a row when something interview-worthy happens.

| Date | Type | Summary |
|------|------|---------|
| 2026-06-22 | Fix | SEC Files: XBRL-only (no EBITDA/FCF/etc. derivations); AMD COGS was sum of duplicate CostOfGoodsAndServicesSold lines — now pick best tag; dedup `xbrl_only`. |
| 2026-06-22 | Bugfix | 5Y annual showed 4 cols: `filter_financials` used fiscal years from quarterly (e.g. FY2026 Q1), dropping oldest annual year. Annual filter now uses annual periods only; quarterly cap = max_years×4; dedup key `periods=v2`. |
| 2026-06-22 | Feature | EdgarTools XBRLS ingest: `standard_concept` → canonical file fields; companyfacts fallback; DCF auto-prefill from SEC; dedup key `ingest=edgartools`. |
| 2026-06-22 | Bugfix | SEC period bucketing: bucket by `end` date not filing `fy`; latest filed wins (not largest value). Fixes AMD FY2023+ mis-assignment; rules in `ingest/SEC_NORMALIZE_RULES.md`. |
| 2026-06-22 | Feature | SEC metric catalog + coverage reports: us-gaap/dei aliases, ProfitLoss→net_income, derivations, field_status reasons; Finnhub lazy env fix; canonical statement UI. |
| 2026-06-22 | Fix | Dashboard poll missed in-place file refresh — `update_file_entry` now sets `updated_at`; workspace `updated_at` uses max(created_at, updated_at). |
| 2026-06-22 | Fix | SEC dedup refresh: re-fetch + `update_file_entry` on duplicate scope (stale AMD revenue after normalize fix); Finnhub via `httpx` (SSL on macOS). |
| 2026-06-22 | Fix | SEC normalize: try all XBRL aliases per FY bucket (AMD revenue); pick best duplicate fact; derive revenue/EBITDA/FCF with `source` metadata; subtle † in StatementViewer. |
| 2026-06-21 | Feature | Phase 3: model-agnostic MCP instructions; comparative analysis + Finnhub; comps dashboard. |
| 2026-06-18 | Feature | Phase 2 SEC: `resolve_ticker` + `fetch_sec_financials` MCP tools; XBRL normalize; session-scoped files with dedup; 1h TTL; StatementViewer in dashboard. |
| 2026-06-18 | Decision | SEC data source: EDGAR `companyfacts` API (not Yahoo); session folders only — no global ticker cache on disk. |
| 2026-06-18 | Decision | File dedup by scope key (`ticker|years|periods|statements`) — repeat fetch returns existing sidebar entry. |
| 2026-06-18 | Deploy | Production live: Render `mcp-financial-model-builder.onrender.com` + EC2 DuckDNS (`myfmdc-api/mcp`) + Caddy/systemd. Render auto-deploys; EC2 manual `update-ec2.sh`. |
| 2026-06-18 | Doc | EC2 deploy runbook: `DEPLOY.md`, `deploy/aws/README.md`. |
| 2026-06-17 | Decision | Deploy split: Render **Static Site** (frontend, no cold start) + Oracle Always Free VM (API + MCP always on). Not Render web service for backend. |
| 2026-06-17 | Decision | Anonymous sessions: UUID folder per user, no login; security = unguessable URL (demo). |
| 2026-06-17 | Decision | HTTP MCP from day one (`http://localhost:8080/mcp`); Cursor uses `url` not stdio — same pattern deploys to Render/GCP. |
| 2026-06-17 | Decision | Three-tool workflow + server input bundle: set_model_inputs before run_dcf; server rejects incomplete builds. |
| 2026-06-17 | Decision | MCP-first fresh start; one `run_dcf` tool; manual inputs Phase 1; JSON store for cross-process sharing. |
| 2026-06-17 | Decision | Local stdio MCP now; streamable-http later for Render/GCP — same tool handlers. |
| 2026-06-17 | Doc | Initial plan, learnings doc, and cursor rule created. |

---

## Not yet done (honest gaps)

- SEC → DCF input prefill (Phase 4)
- LTM/TTM rolling multiples for comps
- Filing HTML/PDF narrative viewer
- Auth for public MCP endpoint
