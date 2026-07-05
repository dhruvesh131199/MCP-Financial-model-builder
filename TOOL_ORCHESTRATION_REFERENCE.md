# MCP Financial Models - Tool Orchestration Reference

This document explains how the current MCP tools are wired, which functions they call, what inputs they accept, and what side effects they produce.

It is intended as a practical map for improving orchestration behavior.

---

## Short Answer to Your Main Question

**Updated (2026-07-02):** Fetch and Detailed Analysis are **decoupled**.

- `fetch_report(report_type="just_financials", ...)` only updates Files/cache (`inputs/statements.json`, ticker-deduped file entry).
- `run_detailed_analysis` fetches SEC data if needed, **then** builds the Detailed Analysis model.

Previously, a 5-year `just_financials` fetch auto-synced Detailed Analysis via `should_sync_detailed_analysis_on_fetch` — that path was removed.

---

## Historical note (pre-decouple)

Yes - in older code, fetching 5-year structured financials could also create/update a Detailed Analysis model.

Why it happened:
- `fetch_report(report_type="just_financials", max_years=5)` routed into `_handle_cached_sec_fetch(...)`.
- `_handle_cached_sec_fetch(...)` called `should_sync_detailed_analysis_on_fetch(...)`.
- If all of these were true:
  - `max_years >= 5`
  - `include_annual == true`
  - statements include all three: `income`, `balance`, `cashflow`
- then it called `save_detailed_analysis_from_cache(...)`, which wrote a Detailed Analysis model.

That coupling is removed; use `run_detailed_analysis` explicitly for the report panel.

---

## Current MCP Tool Surface (active)

From current MCP descriptors, the active tools are:
- `start_session`
- `resolve_ticker`
- `fetch_report`
- `run_detailed_analysis`
- `run_comparative_analysis`
- `create_dcf_model`
- `query_rag`

---

## High-Level Call Graph

```text
start_session
  -> start_session_resolve(session_id?)
  -> create_session() if blank; attach if exists; error if not found

all other tools
  -> require_session(session_id) — error if missing/invalid/not found
  -> _tool_response(session_id, data)

fetch_report
  -> run_fetch_report
     -> just_financials:
        -> _handle_cached_sec_fetch
           -> fetch_and_cache_statements
           -> build_scope_applied + financials_summary
     -> full_report:
        -> resolve_or_ingest_sec (RAG ingestion/linking)

run_detailed_analysis
  -> run_detailed_analysis_for_session
     -> fetch_and_cache_statements
     -> save_detailed_analysis_from_cache
        -> build_detailed_snapshot_from_financials
        -> build_trend_from_snapshot
        -> save_detailed_analysis_model

run_comparative_analysis
  -> handle_run_comparative_analysis
     -> ensure_comparative_sec_files
        -> fetch_and_cache_statements (2-year annual auto fetch if needed)
     -> build_comparative_report
     -> save_comparative_model

create_dcf_model
  -> create_dcf_draft
     -> fetch_and_cache_statements (always 5-year annual reference)
     -> build_dcf_reference_history
     -> save_dcf_draft_model

query_rag
  -> run_query_rag
     -> retrieve: embed_texts -> search_sub_chunks_global -> rerank_hits -> load_parent_chunk -> rag_query_state.json
     -> finalize: merge deduped parents -> combined_context -> clear state
     -> reset: clear rag_query_state.json
```

---

## Session management (2026-07-05 HITL)

- **No** silent auto-create on workspace tools — only `start_session` creates a new folder.
- Host must ask before first tool: *"Do you have an existing session id from your dashboard, or should I create a new workspace?"*
- User pastes UUID from dashboard Session id box or `/s/{uuid}` → pass on every tool call.
- User wants new → `start_session()` with no `session_id`, then use returned id.

**Error codes** (`session_id: null` in envelope):

| Code | When |
|------|------|
| `session_required` | Tool called without `session_id` |
| `session_not_found` | UUID valid but folder missing (expired/deleted) |
| `session_invalid` | Not a valid UUID format |

**Success envelope:**

```json
{
  "session_id": "uuid",
  "data": { "view_url": "...", "...": "..." },
  "system_note": "CRITICAL: Pass session_id from every tool response..."
}
```

Module: [`backend/session_resolve.py`](backend/session_resolve.py) — `require_session`, `start_session_resolve`

---

## Tool-by-Tool Details

## `start_session`

**Purpose**
- Create or attach to a workspace and return dashboard URL.

**Inputs**
- `session_id?: string` — omit for new workspace; pass UUID to reopen existing

**Main function chain**
- `start_session(...)`
  - `start_session_resolve(session_id?)`
  - `_touch_session_writes()`

**Writes / side effects**
- Session lifecycle maintenance (cleanup).
- Returns envelope with `data.view_url`, `data.created_new`, `data.reused_existing`.

---

## `resolve_ticker`

**Purpose**
- Resolve company name/ticker into canonical SEC identity.

**Inputs**
- `company_name?: string`
- `ticker?: string`
- `session_id?: string`

**Main function chain**
- `resolve_ticker(...)` (MCP tool)
  - `sec_resolve_ticker(...)`

**Writes / side effects**
- None (lookup only).

---

## `fetch_report`

**Purpose**
- Unified fetch entrypoint with 2 modes:
  - `just_financials` (Files/XBRL structured tables)
  - `full_report` (RAG full 10-K markdown)

**Inputs**
- `report_type: "just_financials" | "full_report"`
- `tickers: string[]`
- `years?: int[]`
- `max_years?: int` (default 1)
- `session_id?: string`

**Main function chain**
- `fetch_report(...)` (MCP tool)
  - `run_fetch_report(...)`
    - `report_type="just_financials"`:
      - `_handle_cached_sec_fetch(...)`
        - `fetch_and_cache_statements(...)`
        - `upsert_ticker_file_from_cache(...)`
        - `build_scope_applied(...)`
        - `financials_summary(...)`
    - `report_type="full_report"`:
      - if `years` missing: `list_10k_fiscal_years(...)`
      - `resolve_or_ingest_sec(session_id, ticker, fiscal_year=year)`

**Writes / side effects**
- `just_financials`:
  - updates statement cache
  - upserts Files entry only (no Detailed Analysis)
- `full_report`:
  - updates/links RAG document index and chunks

**Important coupling**
- 5-year all-statements annual fetch can write Detailed Analysis.

---

## `run_detailed_analysis`

**Purpose**
- Build curated analysis model (+ trend table) in Detailed Analysis panel.

**Inputs**
- `company_name?: string`
- `ticker?: string`
- `fiscal_years?: int[]`
- `max_years?: int` (default 5)
- `session_id?: string`

**Main function chain**
- `run_detailed_analysis(...)` (MCP tool)
  - `run_detailed_analysis_for_session(...)`
    - `resolve_ticker(...)`
    - `fetch_and_cache_statements(...)`
    - `save_detailed_analysis_from_cache(...)`
      - `materialize_ticker_file_view(...)`
      - `build_detailed_snapshot_from_financials(...)`
      - `build_trend_from_snapshot(...)`
      - `save_detailed_analysis_model(...)`

**Writes / side effects**
- updates cache and Files entry for ticker
- writes/updates Detailed Analysis model

---

## `run_comparative_analysis`

**Purpose**
- Build comparative model (target + peers) including SEC fundamentals + market multiples.

**Inputs**
- `values?: object`
  - `target`, `peers`, optional `fiscal_year`, optional manual `link`
- `session_id?: string`

**Main function chain**
- `run_comparative_analysis(...)` (MCP tool)
  - `handle_run_comparative_analysis(...)`
    - optional `handle_set_comparative_inputs(...)`
    - `ensure_comparative_sec_files(...)`
      - `fetch_and_cache_statements(...)` for last 2 years if needed
      - `apply_comparative_file_links(...)`
    - `build_comparative_report(...)`
    - `save_comparative_model(...)`

**Writes / side effects**
- may auto-fetch and cache SEC files (2 years) for companies
- writes comparative model entry

---

## `create_dcf_model`

**Purpose**
- Create editable DCF draft (dashboard HITL flow).

**Inputs**
- `ticker: string` (required)
- `projection_years: int` (required, 1..10)
- `company_name?: string`
- `session_id?: string`

**Main function chain**
- `create_dcf_model(...)` (MCP tool)
  - `create_dcf_draft(...)`
    - `resolve_ticker(...)`
    - `fetch_and_cache_statements(... max_years=5, annual only ...)`
    - `build_dcf_reference_history(...)`
    - `save_dcf_draft_model(...)`

**Writes / side effects**
- updates cache and Files for ticker
- creates DCF draft model with empty/partially hinted inputs

---

## `query_rag`

**Purpose**
- Host-driven loop retrieval over Postgres 10-K corpus (narrative Q&A).
- Python returns parent chunk context only — host writes the final answer.

**Inputs**
- `mode: "retrieve" | "finalize" | "reset"` (required)
- `query?: string` (required on retrieve — host crafts each loop)
- `ticker?: string` (required on loop 1 retrieve — locks scope for the run; omitted on loops 2+)
- `original_question?: string` (optional loop 1)
- `top_k?: int` (default 10 sub-chunks per loop)
- `session_id?: string`

**Main function chain**
- `query_rag(...)` (MCP tool)
  - `run_query_rag(...)`
    - `retrieve`: `embed_texts` → `search_sub_chunks_global(ticker=...)` (exclude collected parents) → `rerank_hits` → `load_parent_chunk` → `rag_query_state.json`
    - `finalize`: dedupe parents → `combined_context` + `citations` → clear state
    - `reset`: clear state

**Writes / side effects**
- `data/sessions/{uuid}/rag_query_state.json` during retrieve loops (includes locked `ticker`)
- Cleared on finalize/reset
- Requires `DATABASE_URL`, `HF_TOKEN`, Postgres embeddings from `fetch_report(full_report)`

**Host loop rule**
- Loop 1: pass `ticker` (e.g. NVDA). Loops 2+: omit ticker (reused from state).
- After each retrieve, read `new_parent.content`. If more info needed or parent cross-references another section → retrieve again with new query. Else finalize.
- After finalize, append **Sources:** line using `citations[].label`.

---

## Behavior Matrix (what writes where)

| Tool | Files panel | Detailed Analysis panel | Comparative model | DCF draft | RAG 10-K |
|---|---|---|---|---|---|
| `start_session` | no | no | no | no | no |
| `resolve_ticker` | no | no | no | no | no |
| `fetch_report(just_financials)` | yes | no | no | no | no |
| `fetch_report(full_report)` | no | no | no | no | yes |
| `run_detailed_analysis` | yes | yes | no | no | no |
| `run_comparative_analysis` | maybe (auto-fetch for gaps) | no | yes | no | no |
| `create_dcf_model` | yes (reference cache/file) | no | no | yes | no |
| `query_rag` | no | no | no | no | reads Postgres corpus |

---

## Why You Saw Unexpected Detailed Analysis

The trigger is in:
- `backend/services/detailed_analysis_service.py`
  - `should_sync_detailed_analysis_on_fetch(...)`

Current rule:
- if fetch request looks like a full multi-year annual pull (>=5 years and all 3 statements), then sync Detailed Analysis automatically.

This is likely meant as convenience, but it creates orchestration ambiguity.

---

## Recommended Improvements (orchestration-focused)

**Done (2026-07-02):** fetch and Detailed Analysis decoupled — `just_financials` no longer auto-writes Detailed Analysis.

**Still useful:**

1) Add response field for side effects
- For every tool response, include:
  - `side_effects: ["files_updated", "detailed_analysis_updated", ...]`
- Makes host orchestration deterministic.

2) Keep `run_detailed_analysis` as sole writer for Detailed Analysis
- One tool, one panel responsibility.

3) Tighten docs in MCP tool descriptors
- Docstrings in `backend/mcp/server.py` + `INSTRUCTIONS` block.

---

## Suggested Orchestration Rules (host-side)

0. No session_id from a prior tool response this chat:
- ask: "Do you have an existing session id from your dashboard, or should I create a new workspace?"
- user has UUID → pass `session_id` on every call
- user wants new → `start_session()` first

1. User asks "financials", "tables", "last N years":
- call `fetch_report(report_type="just_financials", ...)`
- do not infer detailed analysis unless user asks

2. User asks "detailed analysis", "in depth", "trend table":
- call `run_detailed_analysis(...)`

3. User asks "annual report", "10-K", "risk factors", "MD&A":
- call `fetch_report(report_type="full_report", ...)`

4. User asks "compare X vs Y":
- call `run_comparative_analysis(values=...)`

5. User asks "build DCF":
- ask `projection_years`
- call `create_dcf_model(...)`

6. User asks narrative 10-K question (risks, MD&A, footnotes):
- ensure corpus via `fetch_report(full_report)` if needed
- loop 1: `query_rag(mode="retrieve", ticker="NVDA", query="...")`
- loops 2+: `query_rag(mode="retrieve", query="...")` (ticker reused from state)
- read each parent; refine query if cross-referenced or incomplete
- `query_rag(mode="finalize")` → answer from `combined_context`; append Sources from `citations`

---

## Relevant Source Files

- MCP entrypoint and tool definitions:
  - `backend/mcp/server.py`
- Unified fetch orchestrator:
  - `backend/mcp/fetch_report.py`
- SEC structured financials fetch/cache:
  - `backend/services/sec_financials.py`
- Detailed analysis build/sync logic:
  - `backend/services/detailed_analysis_service.py`
- Comparative orchestration:
  - `backend/services/comparative.py`
- DCF draft lifecycle:
  - `backend/services/dcf_service.py`
- Loop RAG retrieval:
  - `backend/mcp/query_rag.py`
  - `backend/services/rag_loop_retrieval.py`
  - `backend/services/rag_vector_search.py`
  - `backend/services/rag_rerank.py`
  - `backend/rag_query_state.py`

---

## Notes

- This reference reflects current behavior on the code version where the MCP tools listed above are exposed.
- If tool surface changes again, update this file first, then host prompts/instructions.
