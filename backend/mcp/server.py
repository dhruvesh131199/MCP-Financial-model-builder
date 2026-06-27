"""MCP server over HTTP. Anonymous sessions — auto-created per chat connection."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

from ingest.edgar_identity import ensure_edgar_identity

ensure_edgar_identity()

from mcp.server.fastmcp import Context, FastMCP

from engine.dcf import compute_dcf
from engine.dcf_prefill import dcf_still_required, suggest_dcf_inputs
from ingest.normalize import FinancialStatements
from services.sec_client import resolve_ticker as sec_resolve_ticker
from services.sec_financials import (
    build_scope_applied,
    fetch_and_cache_statements,
    financials_summary,
)
from services.detailed_analysis_service import (
    run_detailed_analysis_for_session,
    save_detailed_analysis_from_cache,
    should_sync_detailed_analysis_on_fetch,
)
from services.trend_analysis_service import run_trend_analysis_for_session
from services.comparative import handle_run_comparative_analysis, handle_set_comparative_inputs
from session_binding import resolve_workspace_session
from store import (
    REQUIRED_DCF_FIELDS,
    build_dcf_inputs_from_bundle,
    cleanup_expired_sessions,
    company_name_from_bundle,
    merge_model_inputs,
    save_dcf_model,
    summarize_input_bundle,
)

VIEW_BASE_URL = os.getenv("VIEW_BASE_URL", "http://localhost:5173").rstrip("/")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))

INSTRUCTIONS = """
You help users with financial modeling in a private workspace: DCF valuation, SEC financials,
detailed analysis reports, and peer comparative analysis.

CAPABILITIES:
1. DCF — set_model_inputs + run_dcf (human-in-the-loop — see DCF rules)
2. SEC filings (Files panel) — fetch_sec_financials, fetch_sec_income/balance/cashflow
3. Detailed Analysis (report panel) — run_detailed_analysis ONLY (see routing below)
4. Peer comparison — set_comparative_inputs + run_comparative_analysis (auto-fetch/link SEC files)

DCF — HUMAN IN THE LOOP (strict):
- SEC fetch returns dcf_suggestions only — they are NOT saved. Never copy suggestions into set_model_inputs.
- Ask the user for WACC, terminal growth, NWC %, projection years, and any missing required fields.
- set_model_inputs: pass ONLY keys the user explicitly stated in chat.
- Do NOT call run_dcf until set_model_inputs returns ready=true.

DETAILED ANALYSIS — REQUIRED ROUTING (do not substitute fetch_sec_financials):
When the user asks for detailed analysis, a detailed report, curated 5-year analysis,
in-depth financial breakdown, or similar — call run_detailed_analysis, NOT fetch_sec_financials.

| User says | Tool | Parameters |
|-----------|------|------------|
| "Detailed analysis for Apple" / "analyze AAPL in detail" | run_detailed_analysis | ticker="AAPL" (default max_years=5) |
| "Detailed analysis last 3 years" | run_detailed_analysis | max_years=3 |
| "Detailed analysis FY2023" | run_detailed_analysis | fiscal_years=[2023] |
| "Run detailed analysis" (company already in context) | run_detailed_analysis | ticker from context |

run_detailed_analysis fills the **Detailed Analysis** sidebar (curated income/balance/cashflow report
plus Trend analysis table). fetch_sec_financials fills **Files** only (raw XBRL browse/compare) —
use for single-year fetch, quarterly, or comparative prep, NOT when the user asked for detailed analysis.

TREND ANALYSIS ROUTING:
| User says | Tool |
|-----------|------|
| "detailed analysis for AAPL" | run_detailed_analysis (includes trend) |
| "update trend analysis" / "trend table only" / "refresh trend" | run_trend_analysis |

SEC FETCH — map user words to fetch_sec_financials parameters:
| User says | Parameters |
|-----------|------------|
| "Fetch Apple reports" / latest financials | defaults (max_years=1, include_annual=true, include_quarterly=false) |
| "Apple 2023" / "FY2023 report" | fiscal_years=[2023], include_annual=true, include_quarterly=false |
| "Last 5 years" (raw SEC data, NOT detailed analysis) | max_years=5, include_annual=true; add include_quarterly=true only if user asks quarterly |
| "Quarterly" / "last 4 quarters" | include_annual=false, include_quarterly=true, max_years=1 |
| "Apple 2023 quarterly" | fiscal_years=[2023], include_annual=false, include_quarterly=true |
| Peer comparison (each company) | max_years=2, include_quarterly=false — ONE company per call, sequentially (2 years for YoY growth) |

SEC FETCH RULES:
- Use fiscal_years=[...] when the user names specific years. Use max_years=N for "last N years".
- Do not pass both unless intentional. When fiscal_years is set, max_years does not pick the year.
- After fetch, read scope_applied in the response to confirm the right periods were stored.
- Fiscal year is the company's FY (e.g. Apple FY2025 ends ~Sep 2025), not always calendar year.

UNIVERSAL RULES:
1. start_session() — ALWAYS first for any workspace task. Share view_url after EVERY tool call.
2. Python computes all math — never calculate valuations or ratios in prose.
3. Never invent numbers or tickers — use only what the user stated or tools returned.
4. Always tell the user the next step from the latest tool response message.

Workflow details live in each tool's docstring — read the tool you are about to call.
"""

mcp = FastMCP(
    "financial-models",
    instructions=INSTRUCTIONS,
    host=MCP_HOST,
    port=MCP_PORT,
)


def _view_url(session_id: str) -> str:
    return f"{VIEW_BASE_URL}/s/{session_id}"


def _with_session(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "view_url": _view_url(session_id),
        **payload,
    }


def _touch_session_writes() -> None:
    cleanup_expired_sessions()


@mcp.tool()
def start_session(ctx: Context) -> dict:
    """
    REQUIRED first step for any workspace task. Creates or reuses this chat's workspace.
    Returns view_url — share it immediately so the user can open their private dashboard.
    """
    session_id = resolve_workspace_session(ctx)
    _touch_session_writes()
    url = _view_url(session_id)
    return {
        "session_id": session_id,
        "view_url": url,
        "message": (
            f"Workspace ready. Open your dashboard: {url} "
            "What would you like to do — build a DCF, fetch SEC financials (Files), "
            "run detailed analysis (Detailed Analysis report), or run a peer comparison?"
        ),
    }


@mcp.tool()
def set_model_inputs(
    values: dict[str, Any],
    ctx: Context,
    session_id: str | None = None,
) -> dict:
    """
    Record user-stated DCF assumptions on the server. Call after the user provides numbers.

    DCF RULES (human-in-the-loop):
    - Pass ONLY keys the user explicitly stated in chat. Never use dcf_suggestions from SEC fetch.
    - Ask the user for every missing required field before calling this tool.
    - Allowed keys: base_revenue, revenue_growth, ebitda_margin, tax_rate, capex_pct,
      nwc_pct, wacc, terminal_growth, projection_years, net_debt, shares_outstanding,
      company_name
    - Required fields: """ + ", ".join(REQUIRED_DCF_FIELDS) + """
    - Returns missing_required and ready. If ready=false, ask the user for missing fields.
    - Do NOT call run_dcf until ready=true.
    """
    try:
        sid = resolve_workspace_session(ctx, session_id)
    except ValueError as exc:
        return {"error": str(exc)}

    if not values:
        return _with_session(
            sid,
            {
                "error": "values object is required",
                "example": {"wacc": 0.10, "terminal_growth": 0.02},
            },
        )

    try:
        _touch_session_writes()
        summary = merge_model_inputs(sid, values)
    except KeyError:
        return {"error": "Session not found. Call start_session first."}

    msg = (
        "All required inputs recorded. Call run_dcf() now."
        if summary["ready"]
        else f"Still need from user: {', '.join(summary['missing_required'])}"
    )
    return _with_session(sid, {**summary, "message": msg})


@mcp.tool()
def run_dcf(ctx: Context, session_id: str | None = None) -> dict:
    """
    Build the DCF from inputs already stored via set_model_inputs. Does NOT accept
    inline numbers — the server enforces that inputs were recorded first.

    If not ready, returns missing_required instead of computing.
    Python computes all math; never calculate EV or FCF yourself.
  """
    try:
        sid = resolve_workspace_session(ctx, session_id)
    except ValueError as exc:
        return {"error": str(exc)}

    summary = summarize_input_bundle(sid)
    if not summary["ready"]:
        return _with_session(
            sid,
            {
                "success": False,
                "missing_required": summary["missing_required"],
                "filled": summary["filled"],
                "message": (
                    "Cannot run DCF yet. Ask the user for missing_required fields, "
                    "then call set_model_inputs before run_dcf."
                ),
            },
        )

    try:
        inputs = build_dcf_inputs_from_bundle(sid)
    except ValueError as exc:
        return _with_session(sid, {"success": False, "error": str(exc)})

    company_name = company_name_from_bundle(sid)
    result = compute_dcf(inputs, company_name=company_name)
    _touch_session_writes()
    entry = save_dcf_model(sid, result.model_dump())
    url = _view_url(sid)

    return {
        "success": True,
        "session_id": sid,
        "view_url": url,
        "model_id": entry["id"],
        "model_name": entry["name"],
        "enterprise_value_millions": result.enterprise_value,
        "equity_value_millions": result.equity_value,
        "price_per_share": result.price_per_share,
        "message": f"DCF '{entry['name']}' saved. Open {url} to view and download.",
    }


@mcp.tool()
def resolve_ticker(
    ctx: Context,
    company_name: str | None = None,
    ticker: str | None = None,
    session_id: str | None = None,
) -> dict:
    """
    Resolve a US public company name or ticker symbol to SEC listing metadata.
    Use when the user says a company name (e.g. "Apple", "Tesla") and you need the ticker.
    At least one of company_name or ticker is required.
    """
    try:
        sid = resolve_workspace_session(ctx, session_id)
    except ValueError as exc:
        return {"error": str(exc)}

    result = sec_resolve_ticker(company_name=company_name, ticker=ticker)
    if "error" in result:
        return _with_session(sid, result)
    return _with_session(
        sid,
        {
            **result,
            "message": (
                f"Resolved {result['entity_name']} as {result['ticker']} "
                f"(CIK {result['cik']})."
            ),
        },
    )


def _handle_cached_sec_fetch(
    sid: str,
    *,
    company_name: str | None,
    ticker: str | None,
    fiscal_years: list[int] | None,
    max_years: int,
    include_annual: bool,
    include_quarterly: bool,
    statements: list[str],
) -> dict:
    resolved = sec_resolve_ticker(company_name=company_name, ticker=ticker)
    if "error" in resolved:
        return resolved

    sym = resolved["ticker"]

    _touch_session_writes()

    try:
        financials, gaps_filled, had_fetch, file_id, file_name = fetch_and_cache_statements(
            sid,
            company_name=company_name,
            ticker=ticker,
            fiscal_years=fiscal_years,
            max_years=max_years,
            include_annual=include_annual,
            include_quarterly=include_quarterly,
            statements=statements,
        )
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {
            "error": f"SEC fetch failed for {sym}: {exc}",
            "hint": "Retry one company at a time; on small EC2 try include_quarterly=false.",
        }

    dcf_suggested = suggest_dcf_inputs(financials)
    input_summary = summarize_input_bundle(sid)
    dcf_response = {
        "dcf_suggestions": dcf_suggested,
        "dcf_still_required": input_summary.get("missing_required")
        or dcf_still_required(input_summary.get("filled") or {}),
        "dcf_hitl_note": (
            "dcf_suggestions are read-only hints — ask the user before set_model_inputs; "
            "never pass suggested values unless the user explicitly stated them."
        ),
    }

    scope = build_scope_applied(
        fiscal_years=fiscal_years,
        max_years=max_years,
        include_annual=include_annual,
        include_quarterly=include_quarterly,
        statements=statements,
        financials=financials,
    )
    summary = financials_summary(financials, scope_applied=scope)
    cache_note = (
        " (from session cache)" if not had_fetch and not gaps_filled else ""
    )

    analysis_sync: dict | None = None
    if should_sync_detailed_analysis_on_fetch(
        max_years=max_years,
        include_annual=include_annual,
        statements=statements,
    ):
        analysis_sync = save_detailed_analysis_from_cache(
            sid, sym, max_years=max_years
        )

    response = {
        **summary,
        **dcf_response,
        "file_id": file_id,
        "file_name": file_name,
        "deduplicated": True,
        "refreshed": bool(had_fetch or gaps_filled),
        "statements_cached": not had_fetch and not gaps_filled,
        "gaps_filled": gaps_filled,
        "message": (
            f"Saved '{file_name}' to Files{cache_note}. "
            f"This fetch scope: FY {scope['fiscal_years_included']}; "
            f"quarterly FYs: {scope['quarterly_fiscal_years_included'] or 'none'}. "
            f"Open {_view_url(sid)} to browse."
        ),
    }
    if analysis_sync:
        response["analysis_id"] = analysis_sync["analysis_id"]
        response["analysis_name"] = analysis_sync["analysis_name"]
        response["periods_count"] = analysis_sync["periods_count"]
        response["message"] = (
            f"Saved '{file_name}' to Files and Detailed Analysis ({analysis_sync['periods_count']} periods)"
            f"{cache_note}. Open {_view_url(sid)} → Detailed Analysis sidebar."
        )
    return response


@mcp.tool()
def fetch_sec_financials(
    ctx: Context,
    company_name: str | None = None,
    ticker: str | None = None,
    fiscal_years: list[int] | None = None,
    max_years: int = 1,
    include_annual: bool = True,
    include_quarterly: bool = False,
    statements: list[str] | None = None,
    session_id: str | None = None,
) -> dict:
    """
    Fetch official SEC financial statements for a US public company and save to the
    session Files panel on the dashboard.

    NOT FOR DETAILED ANALYSIS: If the user asked for "detailed analysis", a detailed report,
    or an in-depth curated breakdown — call run_detailed_analysis instead. This tool is for
    raw SEC Files browsing (single year, quarterly, comparative prep).

    PARAMETER GUIDE (max_years default 1, include_quarterly default false):
    - Latest annual only: omit optional scope args (or max_years=1).
    - Specific FY: fiscal_years=[2023] — targeted 10-K, not latest year.
    - Last N years: max_years=N — do not use when user named a specific year.
    - Quarterly only (last 4 quarters): include_annual=false, include_quarterly=true.
    - Named year quarterly: fiscal_years=[2023], include_annual=false, include_quarterly=true.
    - Annual + quarterly history: max_years=N, include_annual=true, include_quarterly=true.

    USER PHRASE → CALL EXAMPLES:
    | User says | Call |
    | "Fetch Apple reports" | company_name="Apple" |
    | "Apple 2023 report" | ticker="AAPL", fiscal_years=[2023] |
    | "Last 5 years annual" | ticker="AAPL", max_years=5 |
    | "Last 4 quarters" | ticker="AAPL", include_annual=false, include_quarterly=true |
    | "AMD FY2023 quarterly" | ticker="AMD", fiscal_years=[2023], include_annual=false, include_quarterly=true |

    SEC RULES:
    - Independent of DCF and comparative — no other inputs required.
    - Peer comparison: ONE company per call, max_years=2, include_quarterly=false (prior year for revenue growth YoY).
    - statements optional: income, balance, cashflow (default all three).
    - Values are SEC XBRL only in Files — host must not calculate or invent figures.
    - Response includes scope_applied — verify fiscal_years_included matches user intent.
    - Returns file_id — link via set_comparative_inputs(link={{ticker, file_id}}).
  """
    try:
        sid = resolve_workspace_session(ctx, session_id)
    except ValueError as exc:
        return {"error": str(exc)}

    if not company_name and not ticker:
        return _with_session(
            sid,
            {"error": "Provide company_name or ticker"},
        )

    stmt_list = statements or ["income", "balance", "cashflow"]
    valid_stmts = [s for s in stmt_list if s in ("income", "balance", "cashflow")]
    if not valid_stmts:
        valid_stmts = ["income", "balance", "cashflow"]

    result = _handle_cached_sec_fetch(
        sid,
        company_name=company_name,
        ticker=ticker,
        fiscal_years=fiscal_years,
        max_years=max_years,
        include_annual=include_annual,
        include_quarterly=include_quarterly,
        statements=valid_stmts,
    )
    return _with_session(sid, result)


def _fetch_sec_statement_tool(
    ctx: Context,
    statement: str,
    *,
    company_name: str | None = None,
    ticker: str | None = None,
    fiscal_years: list[int] | None = None,
    max_years: int = 1,
    include_annual: bool = True,
    include_quarterly: bool = False,
    session_id: str | None = None,
) -> dict:
    try:
        sid = resolve_workspace_session(ctx, session_id)
    except ValueError as exc:
        return {"error": str(exc)}

    if not company_name and not ticker:
        return _with_session(sid, {"error": "Provide company_name or ticker"})

    result = _handle_cached_sec_fetch(
        sid,
        company_name=company_name,
        ticker=ticker,
        fiscal_years=fiscal_years,
        max_years=max_years,
        include_annual=include_annual,
        include_quarterly=include_quarterly,
        statements=[statement],
    )
    return _with_session(sid, result)


@mcp.tool()
def fetch_sec_income(
    ctx: Context,
    company_name: str | None = None,
    ticker: str | None = None,
    fiscal_years: list[int] | None = None,
    max_years: int = 1,
    include_annual: bool = True,
    include_quarterly: bool = False,
    session_id: str | None = None,
) -> dict:
    """Fetch and cache income statement only. Skips SEC call if period leaves already cached."""
    return _fetch_sec_statement_tool(
        ctx,
        "income",
        company_name=company_name,
        ticker=ticker,
        fiscal_years=fiscal_years,
        max_years=max_years,
        include_annual=include_annual,
        include_quarterly=include_quarterly,
        session_id=session_id,
    )


@mcp.tool()
def fetch_sec_balance(
    ctx: Context,
    company_name: str | None = None,
    ticker: str | None = None,
    fiscal_years: list[int] | None = None,
    max_years: int = 1,
    include_annual: bool = True,
    include_quarterly: bool = False,
    session_id: str | None = None,
) -> dict:
    """Fetch and cache balance sheet only. Skips SEC call if period leaves already cached."""
    return _fetch_sec_statement_tool(
        ctx,
        "balance",
        company_name=company_name,
        ticker=ticker,
        fiscal_years=fiscal_years,
        max_years=max_years,
        include_annual=include_annual,
        include_quarterly=include_quarterly,
        session_id=session_id,
    )


@mcp.tool()
def fetch_sec_cashflow(
    ctx: Context,
    company_name: str | None = None,
    ticker: str | None = None,
    fiscal_years: list[int] | None = None,
    max_years: int = 1,
    include_annual: bool = True,
    include_quarterly: bool = False,
    session_id: str | None = None,
) -> dict:
    """Fetch and cache cash flow statement only. Skips SEC call if period leaves already cached."""
    return _fetch_sec_statement_tool(
        ctx,
        "cashflow",
        company_name=company_name,
        ticker=ticker,
        fiscal_years=fiscal_years,
        max_years=max_years,
        include_annual=include_annual,
        include_quarterly=include_quarterly,
        session_id=session_id,
    )


@mcp.tool()
def run_detailed_analysis(
    ctx: Context,
    company_name: str | None = None,
    ticker: str | None = None,
    fiscal_years: list[int] | None = None,
    max_years: int = 5,
    session_id: str | None = None,
) -> dict:
    """
    Build curated Detailed Analysis report for a US public company (5-year default).

    **Use this tool when the user asks for detailed analysis** — not fetch_sec_financials.
    Saves to the dashboard **Detailed Analysis** sidebar: income, balance, and cash flow
    sections in one scrollable report with derived metrics, integrity checks, and a
    **Trend analysis** table (revenue, margins, EPS, YoY growth).

    Uses session statements cache (ticker → period → statement). Fetches only missing
    income/balance/cashflow leaves, syncs Files, then saves type=detailed_analysis.

    USER PHRASE → CALL (always this tool, never fetch_sec_financials):
    | User says | Call |
    | "Detailed analysis for Apple" | run_detailed_analysis(ticker="AAPL") |
    | "Do a detailed analysis on AAPL" | run_detailed_analysis(ticker="AAPL") |
    | "Analyze Microsoft in detail" | run_detailed_analysis(company_name="Microsoft") |
    | "Detailed analysis last 3 years" | run_detailed_analysis(ticker="...", max_years=3) |
    | "Detailed analysis for FY2023" | run_detailed_analysis(ticker="...", fiscal_years=[2023]) |

    WORKFLOW:
    1. start_session() first
    2. run_detailed_analysis(ticker="AAPL", max_years=5) — default 5 annual years
    3. Open view_url → click ticker under **Detailed Analysis** in sidebar

    For partial raw SEC data only (Files panel), use fetch_sec_income / balance / cashflow.
    Repeat calls skip SEC fetch when cache is complete (statements_cached=true).
    """
    try:
        sid = resolve_workspace_session(ctx, session_id)
    except ValueError as exc:
        return {"error": str(exc)}

    if not company_name and not ticker:
        return _with_session(sid, {"error": "Provide company_name or ticker"})

    _touch_session_writes()
    result = run_detailed_analysis_for_session(
        sid,
        company_name=company_name,
        ticker=ticker,
        fiscal_years=fiscal_years,
        max_years=max_years,
    )
    if "error" in result:
        return _with_session(sid, result)

    url = _view_url(sid)
    return _with_session(
        sid,
        {
            **result,
            "view_url": url,
            "message": (
                f"Detailed Analysis saved for {result.get('ticker')}. "
                f"{result.get('periods_count', 0)} periods. "
                f"Open {url} → Detailed Analysis sidebar."
            ),
        },
    )


@mcp.tool()
def run_trend_analysis(
    ctx: Context,
    company_name: str | None = None,
    ticker: str | None = None,
    max_years: int = 5,
    session_id: str | None = None,
) -> dict:
    """
    Rebuild or refresh the Trend analysis table for a ticker (standalone).

    Use when the user asks to update trend analysis only — not a full detailed analysis rerun.
    Requires cached annual statements (from fetch_sec_financials or run_detailed_analysis).
    Upserts the `trend_analysis` block on the ticker's Detailed Analysis model.

    USER PHRASE → CALL:
    | User says | Call |
    | "Update trend analysis for Apple" | run_trend_analysis(ticker="AAPL") |
    | "Refresh trend table" | run_trend_analysis(ticker=...) |
    | "Detailed analysis for Apple" | run_detailed_analysis (includes trend) — NOT this tool |

    WORKFLOW:
    1. start_session() first
    2. run_trend_analysis(ticker="AAPL", max_years=5)
    3. Open view_url → Detailed Analysis → scroll to Trend analysis section
    """
    try:
        sid = resolve_workspace_session(ctx, session_id)
    except ValueError as exc:
        return {"error": str(exc)}

    if not company_name and not ticker:
        return _with_session(sid, {"error": "Provide company_name or ticker"})

    resolved = sec_resolve_ticker(company_name=company_name, ticker=ticker)
    if "error" in resolved:
        return _with_session(sid, resolved)

    _touch_session_writes()
    result = run_trend_analysis_for_session(
        sid,
        resolved["ticker"],
        max_years=max_years,
    )
    if "error" in result:
        return _with_session(sid, result)

    url = _view_url(sid)
    return _with_session(
        sid,
        {
            **result,
            "view_url": url,
            "message": (
                f"Trend analysis updated for {result.get('ticker')}. "
                f"{result.get('trend_row_count', 0)} rows. "
                f"Open {url} → Detailed Analysis → Trend analysis."
            ),
        },
    )


@mcp.tool()
def set_comparative_inputs(
    values: dict[str, Any],
    ctx: Context,
    session_id: str | None = None,
) -> dict:
    """
    Set up a peer comparison: target company + 1–10 peers.

    WORKFLOW:
    1. set_comparative_inputs with target + peers tickers
    2. run_comparative_analysis — auto-fetches last 2 annual years if missing (YoY growth), links ticker Files, builds report

    Optional: fetch_sec_financials per company first; values.link still supported for manual file_id.

    COMPARATIVE RULES:
    - values.target: {{ticker, company_name?}}
    - values.peers: list of {{ticker, company_name?}} (1–10)
    - values.fiscal_year: optional int — same FY for all; omit to use each company's latest annual FY
    - values.link: {{ticker, file_id}} optional when Files already exist
    - run_comparative_analysis fetches Finnhub market data and SEC fundamentals per company
    """
    try:
        sid = resolve_workspace_session(ctx, session_id)
    except ValueError as exc:
        return {"error": str(exc)}

    _touch_session_writes()
    result = handle_set_comparative_inputs(sid, values)
    if "error" in result and "session_id" not in result:
        return _with_session(sid, result)
    return _with_session(sid, result)


@mcp.tool()
def run_comparative_analysis(ctx: Context, session_id: str | None = None) -> dict:
    """
    Build comparative report for target + peers registered via set_comparative_inputs.

    Auto-fetches last 2 annual SEC years per ticker when cache gaps exist (YoY revenue growth),
    links by ticker, uses each company's latest annual FY unless fiscal_year was set.
    """
    try:
        sid = resolve_workspace_session(ctx, session_id)
    except ValueError as exc:
        return {"error": str(exc)}

    _touch_session_writes()
    result = handle_run_comparative_analysis(sid)
    url = _view_url(sid)
    return {**result, "session_id": sid, "view_url": url}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
