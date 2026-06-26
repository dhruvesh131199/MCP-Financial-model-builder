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
| SEC ingest | **Per-filing edgartools statements** | XBRLS stitch + `standard_concept` adapter | Simpler, accurate bank revenue; one `Financials.extract(filing)` per 10-K/10-Q |
| User identity | **Random UUID session** — folder per user | Login/signup; shared latest_model | Demo-friendly; no auth friction; unguessable link = isolation |
| Frontend (Phase 1) | **Single page, poll API** | Full 20/80 sidebar; WebSocket | See model in action fast; sidebar comes Phase 3 |
| Codebase | **Fresh start** | Port entire REST project | Clean MCP architecture; reference sibling for algorithms only |
| Hero / HF eval | **Homework only; no product case study** | Bake HF into SEC ingest | 50-ticker HF test: `smart_revenue` wins; HF rejected for normalization; `homework/huggingface_test/` kept for future experiments |
| Detailed analysis | **`detailed_extract.py` + homework first** | Raw edgartools dump in UI; LLM line picking | Fixed row template (11+8+5 lines × 5 FY); tag-first rules; v1.1 adds **two-phase pick + derive** with provenance metadata (Files panel stays XBRL-only) |

---

## Detailed Analysis v1.1 — extraction logic (interview reference)

Homework + dashboard panel: `backend/ingest/detailed_extract.py`, `DetailedAnalysisPanel`, `homework/detailed_analysis/`.  
Rules also in `backend/ingest/SEC_NORMALIZE_RULES.md`.

### Architecture: two phases

```
edgartools DataFrames → Phase 1: XBRL pickers → Phase 2: apply_detailed_derivations → integrity checks → UI
```

| Phase | What | Rule |
|-------|------|------|
| **1 — Pick** | Walk filed income/balance/cashflow for each template row | Prefer **raw US-GAAP tag + label guards**; `standard_concept` only as fallback |
| **2 — Derive** | Fill nulls when inputs exist | Never overwrite a filed number; mark `source: "derived"` + warning |

**Interview line:** *“Python computes; the host orchestrates. Detailed Analysis is a curated comparison table with controlled derivations — separate from the raw Files ingest, which stays XBRL-only.”*

### Core principle: tag-first, not concept-first

`standard_concept` buckets unrelated rows. Real bugs that drove this:

| Bug | Cause | Fix |
|-----|-------|-----|
| JPM investing CF wrong | Sub-lines (deposits, other) shared investing concept with **total** | Raw tag `NetCashProvidedByUsedInInvestingActivities` only |
| GM COGS too low | Picked automotive segment only | Conglomerate sum (see below) |
| JPM COGS nonsense | `LaborAndRelatedExpense` hit COGS fallback | Skip COGS when revenue is `RevenuesNetOfInterestExpense` |

---

### Income statement — picker order

#### Revenue
`smart_revenue()`: prefer `RevenuesNetOfInterestExpense` (banks) or `Revenues` with total labels (“Total net sales and revenue” for GM). Reject segment-only lines.

#### COGS (`cost_of_revenue`) — tiered

| Step | Rule |
|------|------|
| 0 | Bank revenue tag → **no COGS** (`n/a`) |
| 1 | `CostOfRevenue` + total-style label |
| 2 | Non-segment `CostOfGoodsAndServicesSold` (`dimension == 0` or empty) |
| 3 | **Conglomerate sum (GM):** automotive COGS + `OperatingCostsAndExpenses` where label contains “financial” / “gm financial” → tag `conglomerate_cogs_sum` |
| 4 | Single COGS row if only one (after step 3 fails) |
| 5 | Largest COGS by \|value\| among multiples |
| 6 | `standard_concept` fallback |

**GM FY2025:** $159.1B auto + $14.3B GM Financial ≈ **$173.4B**. Early bug: returned on first single COGS row before checking financial add-on.

#### Gross profit
Filed `GrossProfit` tag → else **derive** `revenue − |COGS|` (`derived_gross_profit`). Fixes **COST** (~$35.3B) and **GM** (~$11.6B).

#### Operating cost — cascade with rejection

| Priority | Source | Guard |
|----------|--------|-------|
| 1 | `OperatingExpenses` “total operating expense” label | **Reject** “Total costs and expenses” (GM $182B full cost block) |
| 2 | `TotalOperatingExpenses` | Same rejection |
| 3 | R&D + SG&A sum | Both present |
| 4 | SG&A alone | **COST** ~$25B |
| 5 | `NoninterestExpense` | Banks — `bank_noninterest_expense` |
| 6 | **Derive** `gross_profit − operating_income` | GM fallback ~$8.7B |

#### EBITDA — derived only
`EBITDA = operating_income + D&A add-back`. Add-back uses depreciation and/or amortization; **never treat missing amortization as zero** — incomplete D&A → no EBITDA.

#### Depreciation / amortization — cross-statement

Depreciation order: income tags (`Depreciation`, `DepreciationAndAmortization`, …) → income `DepreciationExpense` → CF `DepreciationDepletionAndAmortization` → **sum CF rows** where concept/label contains “depreciation” (`cf_depreciation_sum` for GM extension tags).

---

### Banks (JPM, BAC, …)

**Detection:** revenue tag `RevenuesNetOfInterestExpense` OR ticker in `KNOWN_BANK_TICKERS`.

**Behavior:** COGS and gross profit → `n/a`; operating cost → `NoninterestExpense`; UI **bank sector banner**. Prevents compensation expense from being mis-picked as COGS.

---

### Balance sheet

| Row | Picker |
|-----|--------|
| Current / non-current assets & liabilities | `AssetsCurrent`, `AssetsNoncurrent`, etc. + total-style label guards |
| **Total assets / total liabilities** (v1.1) | `Assets` / `Liabilities` + “total …” label — not first sub-line |
| **Cash at period end** (v1.1) | `CashAndCashEquivalentsAtCarryingValue` — **stock** on balance sheet |
| Derived non-current | `total − current` when filed non-current tag missing (**COST** ~$38.7B non-current assets) |

**Accounting equation:** `|A − (L + E)| / A ≤ 2%` → ✓; else ⚠. Flag only — never force-balance. Shown per FY in dashboard + homework HTML.

---

### Cash flow

| Row | Logic |
|-----|--------|
| CFO / CFI / CFF | Raw tags `NetCashProvidedByUsedInOperating/Investing/FinancingActivities` + label needles |
| **Net change in cash (FY)** | CF increase/decrease tags — **flow** during the year |
| **Cash at period end** | On **balance** tab — **stock** at FY-end (different concept; both shown) |
| **FCF** | `operating_cash_flow − |CapEx|` — derived; footnote that Yahoo/other sites may differ |

**GM FCF ~$17.6B vs Yahoo ~$1.8B:** definition mismatch (leases, captive finance, WC), not a simple extraction bug — we keep OCF − |CapEx| from filed XBRL.

**Integrity:** `OCF + CFI + CFF + FX ≈ net cash change` (5% tolerance).

---

### Provenance & UI transparency

Every cell: `xbrl_tag`, filed `label`, `source_statement`, `source` (`xbrl` | `derived` | `n/a`), optional `warning`. Dashboard hover + homework HTML. Global accuracy disclaimer; bank banner; FCF footnote.

---

### Ticker stories (quick anecdotes)

| Ticker | Problem | Fix |
|--------|---------|-----|
| **GM** | Segment COGS; no GP; $182B “total costs” trap; custom D&A tags | Conglomerate COGS sum; derive GP; SG&A not total-costs block; CF D&A sum → EBITDA |
| **COST** | No filed GP or non-current assets | Derive GP; derive non-current from totals |
| **JPM** | Bank layout; wrong investing/COGS | Bank guards; raw CF section tags |
| **AAPL** | Clean industrial baseline | Regression anchor; A=L+E passes |

---

### What we deliberately did not ship (v1.1)

- Inline editable cells (disclaimer only)
- Yahoo FCF parity
- LLM/HF normalization in product path (homework eval only; Python rules win)
- Derived metrics in **Files** panel ingest (stays XBRL-only; derivations only in Detailed Analysis template)

---

### 30-second interview pitch (Detailed Analysis)

> “SEC filers use inconsistent XBRL, so we built a two-phase normalizer: tag-first pickers with label guards for each line in a fixed 5-year template, then conservative derived fallbacks only when filed data is missing. We hit real edge cases — GM needed automotive plus financial COGS summed, banks need COGS suppressed, JPM needed raw cash-flow section tags. Every number carries provenance, we sanity-check A=L+E, and we separate this curated view from raw XBRL in the Files panel so users know what's filed vs derived.”

---

## Chronological journey

### 2026-06-25 — Detailed Analysis v1.1 (accuracy + disclaimers)

- **Trigger:** User review on GM/COST/JPM homework — wrong COGS, missing GP, net cash vs cash-at-end confusion, no EBITDA, no A=L+E check.
- **Approach:** Two-phase extract (pick → derive); conglomerate COGS; reject “Total costs and expenses” as op ex; balance totals + derived non-current; bank guards; global disclaimer.
- **Validated:** pytest on AAPL/GM/COST/JPM fixtures; homework re-run. GM FY2025: COGS $173.4B, GP $11.6B, EBITDA $17.5B.
- **Next:** Wire fully into main product flow (session fetch → dashboard) — homework path proven first.

### 2026-06-25 — HF vs edgartools experiment (concluded — not shipped)

- **Question:** Can an LLM normalize SEC income lines better than edgartools + `smart_revenue()`?
- **Method:** 50 tickers → HF `meta-llama/Meta-Llama-3-8B-Instruct` via `router.huggingface.co/v1`; manual review vs Python rules.
- **Outcome:** **`smart_revenue` wins overall; HF not production-ready** (over-maps Revenue on AAPL; wrong buckets on GM gross profit). Fixed GM in Python (`Total net sales and revenue` on `us-gaap_Revenues`).
- **Decision:** Removed public case study from repo; kept `backend/homework/huggingface_test/` for possible future HF work — **not** in MCP/dashboard path.

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
5. **LLM for SEC normalization** — Evaluated HF on 50 tickers; **rejected for production.** `smart_revenue` + edgartools wins; fixed GM total-revenue label. Homework scaffold remains; no shipped case study.
6. **SEC XBRL is filer-specific** — Detailed Analysis v1.1: tag-first pickers + label guards + second-pass derivations with provenance; conglomerate COGS (GM), bank revenue guard (JPM), CF D&A sum for extension tags. See **Detailed Analysis v1.1** section above.

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
| 2026-06-25 | Fix | Detailed Analysis sidebar empty when host used `fetch_sec_financials(max_years=5)` instead of `run_detailed_analysis` — auto-sync analysis model on full 5Y fetch; build snapshot from full cache; years newest-first in Files + report. |
| 2026-06-25 | Doc | Added **Detailed Analysis v1.1 — extraction logic (interview reference)** section: two-phase pick/derive, per-metric rules, ticker stories, 30s pitch. |
| 2026-06-25 | Feature | Detailed Analysis Phase 2 (main product): hierarchical `inputs/statements.json` cache (ticker→period→statement); decoupled `fetch_sec_income/balance/cashflow`; `run_detailed_analysis` MCP tool; third dashboard sidebar section. |
| 2026-06-25 | Feature | Detailed Analysis v1.1: EBITDA + derived GP/op cost/non-current; GM conglomerate COGS (auto + GM Financial); balance A=L+E check; cash at period end; global disclaimer + bank banner; CF D&A sum for extension tags; bank COGS guard for `RevenuesNetOfInterestExpense`. |
| 2026-06-25 | Feature | Detailed Analysis Phase 1: `ingest/detailed_extract.py` (tag-first pickers for op cost, balance sections, CFIA/CFFA); homework `detailed_analysis/run.py`; merged into `edgar_fetch`; `DetailedAnalysisPanel` on dashboard. |
| 2026-06-25 | Decision | Removed HF case study from product (docs/public/homepage/README); experiment concluded — Python rules win; `homework/huggingface_test/` kept for future HF use. |
| 2026-06-25 | Fix | `smart_revenue`: GM total via `us-gaap_Revenues` + label “Total net sales and revenue” (`_total_revenue_label_ok`); was picking Automotive segment only. |
| 2026-06-25 | Fix | HF homework: migrated from dead `api-inference.huggingface.co` to `router.huggingface.co/v1` via OpenAI SDK (DNS Errno 8 on old host). |
| 2026-06-25 | Feature | HF accuracy homework: `homework/huggingface_test/` — 50-ticker edgartools income baselines + HF Inference API boilerplate + `review_sheet.csv` for manual truth; isolated from main app. |
| 2026-06-24 | Feature | Hero Feature Phase 1 homework: `homework/hero_analysis_explore.py` — XBRLS 5Y all five statement types, HTML/JSON/CSV export; edgartools-native (no production concept_map); dashboard integration deferred. |
| 2026-06-22 | Refactor | SEC ingest simplified: per-filing `income_statement` / `balance_sheet` / `cashflow_statement` + `statement_extract.py`; removed XBRLS stitch, `edgar_adapter`, `edgar_fetch_plan`; JPM bank revenue fixed via total-line rules; dedup `fetch=statements`. |
| 2026-06-21 | Doc | MCP INSTRUCTIONS + fetch_sec_financials phrase→params table; scope_applied in fetch response; comparative numbered workflow. |
| 2026-06-21 | Perf | SEC fetch default `max_years=1`, `include_quarterly=false`; comps fetch latest FY only; MCP instructs sequential one-company fetches; dedup `default=1y`; 1 10-K when max_years≤1. |
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

- **Detailed Analysis in main product flow** — Phase 2 shipped: shared cache + MCP tools + sidebar; trend analysis next
- **Not yet done** → SEC → DCF prefill exists (`suggest_dcf_inputs`); LTM/TTM comps still open
- LTM/TTM rolling multiples for comps
- Filing HTML/PDF narrative viewer
- Auth for public MCP endpoint
