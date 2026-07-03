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

---

## High-Level Call Graph

```text
start_session
  -> resolve_workspace_session

fetch_report
  -> run_fetch_report
     -> just_financials:
        -> _handle_cached_sec_fetch
           -> fetch_and_cache_statements
           -> suggest_dcf_inputs
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
```

---

## Tool-by-Tool Details

## `start_session`

**Purpose**
- Create/reuse session workspace and return dashboard URL.

**Inputs**
- none

**Main function chain**
- `start_session(...)`
  - `resolve_workspace_session(ctx)`
  - `_touch_session_writes()`

**Writes / side effects**
- Session lifecycle maintenance (cleanup).
- Returns `session_id`, `view_url`.

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
        - `suggest_dcf_inputs(...)`
        - `build_scope_applied(...)`
        - `financials_summary(...)`
        - conditional:
          - `should_sync_detailed_analysis_on_fetch(...)`
          - `save_detailed_analysis_from_cache(...)`
    - `report_type="full_report"`:
      - if `years` missing: `list_10k_fiscal_years(...)`
      - `resolve_or_ingest_sec(session_id, ticker, fiscal_year=year)`

**Writes / side effects**
- `just_financials`:
  - updates statement cache
  - upserts Files entry
  - may also write Detailed Analysis model (conditional coupling)
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

## Behavior Matrix (what writes where)

| Tool | Files panel | Detailed Analysis panel | Comparative model | DCF draft | RAG 10-K |
|---|---|---|---|---|---|
| `start_session` | no | no | no | no | no |
| `resolve_ticker` | no | no | no | no | no |
| `fetch_report(just_financials)` | yes | **sometimes yes** (5-year full annual all-statements) | no | no | no |
| `fetch_report(full_report)` | no | no | no | no | yes |
| `run_detailed_analysis` | yes | yes | no | no | no |
| `run_comparative_analysis` | maybe (auto-fetch for gaps) | no | yes | no | no |
| `create_dcf_model` | yes (reference cache/file) | no | no | yes | no |

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

1) Decouple fetch and analysis by default
- Change `should_sync_detailed_analysis_on_fetch` to always return `False`, or gate behind an explicit flag.

2) Add explicit intent flag to `fetch_report`
- Example: `sync_detailed_analysis: bool = false`.
- Only create/update Detailed Analysis when explicitly true.

3) Add response field for side effects
- For every tool response, include:
  - `side_effects: ["files_updated", "detailed_analysis_updated", ...]`
- Makes host orchestration deterministic.

4) Keep `run_detailed_analysis` as sole writer for Detailed Analysis
- Cleaner mental model: one tool, one panel responsibility.

5) Tighten docs in MCP tool descriptors
- In `fetch_report` description, explicitly mention auto-sync behavior if kept.
- Or remove mention if behavior is removed.

---

## Suggested Orchestration Rules (host-side)

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

---

## Notes

- This reference reflects current behavior on the code version where only the 6 MCP tools listed above are exposed.
- If tool surface changes again, update this file first, then host prompts/instructions.
