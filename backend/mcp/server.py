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

import importlib.util
import sys
import os

# Find the installed mcp package
import site
site_packages = site.getsitepackages()[0]
sys.path.insert(0, site_packages)

# Import the real mcp package directly from site-packages
import importlib.machinery
spec = importlib.machinery.PathFinder().find_spec("mcp", [site_packages])
real_mcp = importlib.util.module_from_spec(spec)
sys.modules["real_mcp"] = real_mcp
spec.loader.exec_module(real_mcp)

spec_server = importlib.machinery.PathFinder().find_spec("mcp.server", [os.path.join(site_packages, "mcp")])
real_mcp_server = importlib.util.module_from_spec(spec_server)
sys.modules["real_mcp.server"] = real_mcp_server
spec_server.loader.exec_module(real_mcp_server)

spec_fastmcp = importlib.machinery.PathFinder().find_spec("mcp.server.fastmcp", [os.path.join(site_packages, "mcp", "server")])
real_mcp_server_fastmcp = importlib.util.module_from_spec(spec_fastmcp)
sys.modules["real_mcp.server.fastmcp"] = real_mcp_server_fastmcp
spec_fastmcp.loader.exec_module(real_mcp_server_fastmcp)

Context = real_mcp_server_fastmcp.Context
FastMCP = real_mcp_server_fastmcp.FastMCP

sys.path.pop(0)

from engine.dcf_prefill import suggest_dcf_inputs
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
from services.dcf_service import create_dcf_draft
from mcp.fetch_report import run_fetch_report
from session_binding import resolve_workspace_session
from store import cleanup_expired_sessions

VIEW_BASE_URL = os.getenv("VIEW_BASE_URL", "http://localhost:5173").rstrip("/")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))

INSTRUCTIONS = """
You help users with financial modeling in a private workspace: DCF valuation, SEC financials,
detailed analysis reports, and peer comparative analysis.

CAPABILITIES:
1. DCF — create_dcf_model (dashboard editor — see DCF rules)
2. Fetch SEC data — fetch_report (Files tables OR full 10-K RAG)
3. Detailed Analysis (report panel) — run_detailed_analysis ONLY (see routing below)
4. Peer comparison — set_comparative_inputs + run_comparative_analysis (auto-fetch/link SEC files)

DCF — DASHBOARD HUMAN IN THE LOOP (strict):
- ALWAYS ask the user: "How many years should the DCF forecast cover?" before creating a model.
- NEVER call create_dcf_model without explicit projection_years from the user (1–10).
- create_dcf_model always fetches 5 years of SEC data for the reference panel (independent of forecast length).
- User fills assumptions on the dashboard → clicks Update model. Do NOT collect DCF assumptions in chat.
- SEC fetch returns dcf_suggestions as read-only context only — never auto-save; use create_dcf_model for DCF.

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
plus Trend analysis table). fetch_report(just_financials) fills **Files** only (raw XBRL browse/compare) —
use for single-year fetch, quarterly, or comparative prep, NOT when the user asked for detailed analysis.

TREND ANALYSIS ROUTING:
| User says | Tool |
|-----------|------|
| "detailed analysis for AAPL" | run_detailed_analysis (includes trend) |
| "update trend analysis" / "trend table only" / "refresh trend" | run_trend_analysis |

SEC DATA TYPE — REQUIRED DISAMBIGUATION (fetch_report):
When the user asks to "fetch financials", "get reports", "fetch 10-K", "annual report", or similar:
1. ALWAYS ask: "Do you want structured SEC financial tables (Files panel) or the complete 10-K narrative document (RAG)?"
2. Map answer to report_type:
   - Tables / statements / DCF or comps prep / quarterly → just_financials
   - Full annual report / 10-K document / RAG / narrative / risk factors / MD&A → full_report

| User says | Tool | Parameters |
|-----------|------|------------|
| "Fetch Apple financial statements" / tables for Files | fetch_report | report_type="just_financials", tickers=["AAPL"] |
| "Fetch Apple annual report" / full 10-K for RAG | fetch_report | report_type="full_report", tickers=["AAPL"] |
| "Fetch Walmart 2024 annual report" | fetch_report | report_type="full_report", tickers=["WMT"], years=[2024] |
| "Last 5 years for AAPL and MSFT" | fetch_report | report_type="just_financials", tickers=["AAPL", "MSFT"], max_years=5 |

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
def create_dcf_model(
    ctx: Context,
    ticker: str,
    projection_years: int,
    company_name: str | None = None,
    session_id: str | None = None,
) -> dict:
    """
    Create a DCF model template on the dashboard. REQUIRED before any DCF valuation.

    WORKFLOW:
    1. Ask the user how many forecast years (projection_years) they want — required, no default.
    2. create_dcf_model(ticker="MU", projection_years=5) — fetches 5Y SEC reference, builds N-year grid.
    3. User opens view_url → fills WACC, terminal g, base revenue, per-year rows → Update model.

    RULES:
    - projection_years is REQUIRED (1–10). Never omit or guess.
    - SEC fetch is always 5 years for reference history, regardless of projection_years.
    - Forecast grid has projection_years columns; reference panel always shows 5 fiscal years.
    - Do NOT collect DCF assumptions in chat — dashboard editor only.
    """
    try:
        sid = resolve_workspace_session(ctx, session_id)
    except ValueError as exc:
        return {"error": str(exc)}

    _touch_session_writes()
    result = create_dcf_draft(
        sid,
        ticker=ticker,
        company_name=company_name,
        projection_years=projection_years,
    )
    if "error" in result:
        return _with_session(sid, result)

    url = _view_url(sid)
    n = result.get("projection_years")
    ref = result.get("reference_years", 5)
    return _with_session(
        sid,
        {
            **result,
            "message": (
                f"DCF draft created ({n}-year forecast, {ref}-year SEC reference). "
                f"Open {url} → fill assumptions in the editor → click Update model."
            ),
        },
    )


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
    dcf_response = {
        "dcf_suggestions": dcf_suggested,
        "dcf_hitl_note": (
            "dcf_suggestions are read-only SEC hints. For DCF, ask projection years "
            "and call create_dcf_model — fill assumptions on the dashboard editor."
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
def fetch_report(
    ctx: Context,
    report_type: str,
    tickers: list[str],
    years: list[int] | None = None,
    max_years: int = 1,
    session_id: str | None = None,
) -> dict:
    """
    Fetch financial reports for one or more US public companies.

    REQUIRED DISAMBIGUATION:
    If report_type is unclear, ALWAYS ask: "Do you want structured SEC financial tables (Files panel) or the complete 10-K narrative document (RAG)?"

    report_type MUST be one of:
    - "just_financials": Structured XBRL tables (income/balance/cashflow) in Files panel. Use for DCF, comps, or raw data browsing.
    - "full_report": Entire filed 10-K document as markdown (narrative, risk factors, MD&A, footnotes) for RAG. Saves to RAG sidebar.

    USER PHRASE → CALL EXAMPLES:
    | User says | Call |
    | "Fetch Apple financial statements" / tables for Files | report_type="just_financials", tickers=["AAPL"] |
    | "Fetch Apple annual report" / full 10-K for RAG | report_type="full_report", tickers=["AAPL"] |
    | "Fetch Walmart 2024 annual report" | report_type="full_report", tickers=["WMT"], years=[2024] |
    | "Last 5 years for AAPL and MSFT" | report_type="just_financials", tickers=["AAPL", "MSFT"], max_years=5 |

    YEAR RESOLUTION:
    - years=[2024] → Fetch FY2024 only
    - years=[2023, 2024] → Fetch each listed year
    - years omitted, max_years=N → Last N distinct fiscal years
    - years omitted, max_years=1 (default) → Latest filing only
    """
    try:
        sid = resolve_workspace_session(ctx, session_id)
    except ValueError as exc:
        return {"error": str(exc)}

    _touch_session_writes()
    
    # Cast report_type to Literal to satisfy type checker, validation happens inside run_fetch_report
    from typing import cast
    from mcp.fetch_report import ReportType
    
    return _with_session(
        sid,
        run_fetch_report(
            session_id=sid,
            report_type=cast(ReportType, report_type),
            tickers=tickers,
            years=years,
            max_years=max_years,
        ),
    )


def _fetch_sec_financials_impl(
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

    NOT FOR full 10-K RAG: If the user asked for the complete annual report document
    (narrative, risk factors, MD&A, footnotes for RAG) — call fetch_annual_report instead.
    This tool returns structured XBRL tables only.

    DISAMBIGUATION: When intent is unclear, ask whether they want Files tables or full 10-K RAG.

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


def _fetch_annual_report_impl(
    ctx: Context,
    ticker: str,
    fiscal_year: int | None = None,
    session_id: str | None = None,
) -> dict:
    """
    Fetch a primary 10-K annual report (business, risk factors, MD&A,
    financial statements, footnotes) and convert to markdown for RAG prep.

    NOT the same as fetch_sec_financials:
    - fetch_sec_financials → structured XBRL tables in Files panel (models/comps)
    - fetch_annual_report → entire filed 10-K document as markdown (narrative + statements)

    NOT FOR structured Files/XBRL only — use fetch_sec_financials for statement tables.

    DISAMBIGUATION: When intent is unclear, ask whether they want Files tables or full 10-K RAG.

    USER PHRASE → CALL:
    | User says | Call |
    | "Fetch Apple's annual report" | ticker="AAPL" |
    | "Fetch Walmart 2024 annual report" | ticker="WMT", fiscal_year=2024 |
    | "Get Walmart 10-K for RAG" | ticker="WMT" (latest if year omitted) |

    Saves to session RAG index. Dashboard: RAG sidebar section on view_url.
    """
    try:
        sid = resolve_workspace_session(ctx, session_id)
    except ValueError as exc:
        return {"error": str(exc)}

    sym = (ticker or "").strip().upper()
    if not sym:
        return _with_session(sid, {"error": "ticker is required"})

    try:
        resolved = resolve_or_ingest_sec(
            session_id=sid, ticker=sym, fiscal_year=fiscal_year
        )
    except ValueError as exc:
        return _with_session(sid, {"error": str(exc)})
    except KeyError:
        return _with_session(sid, {"error": "Session not found"})

    if not resolved.success:
        return _with_session(
            sid,
            {
                "success": False,
                "error": resolved.error,
                "filing_key": resolved.filing_key,
                "rag_entry_id": resolved.rag_entry_id,
            },
        )

    doc_id = resolved.document_id
    report_path = f"/api/sessions/{sid}/rag/documents/{doc_id}/report"
    cache_note = " (loaded from library)" if resolved.from_cache else ""
    return _with_session(
        sid,
        {
            "success": True,
            "document_id": doc_id,
            "ticker": sym,
            "from_cache": resolved.from_cache,
            "filing_key": resolved.filing_key,
            "parent_count": resolved.parent_count,
            "subchunk_count": resolved.subchunk_count,
            "items_found": (
                resolved.ingest.section_outline.items_found
                if getattr(resolved, "ingest", None)
                and resolved.ingest
                and resolved.ingest.section_outline
                else None
            ),
            "report_api_path": report_path,
            "message": (
                f"{'Linked' if resolved.from_cache else 'Fetched'} latest 10-K for {sym}"
                f"{cache_note}. Chunks: {resolved.parent_count} parent / "
                f"{resolved.subchunk_count} sub."
            ),
        },
    )


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


def _fetch_sec_income_impl(
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


def _fetch_sec_balance_impl(
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


def _fetch_sec_cashflow_impl(
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

    **Use this tool when the user asks for detailed analysis** — not fetch_report.
    Saves to the dashboard **Detailed Analysis** sidebar: income, balance, and cash flow
    sections in one scrollable report with derived metrics, integrity checks, and a
    **Trend analysis** table (revenue, margins, EPS, YoY growth).

    Uses session statements cache (ticker → period → statement). Fetches only missing
    income/balance/cashflow leaves, syncs Files, then saves type=detailed_analysis.

    USER PHRASE → CALL (always this tool, never fetch_report):
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

    For partial raw SEC data only (Files panel), use fetch_report(just_financials).
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
    Requires cached annual statements (from fetch_report or run_detailed_analysis).
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

    Optional: fetch_report(just_financials) per company first; values.link still supported for manual file_id.

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
