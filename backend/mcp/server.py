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
    build_dedup_key,
    build_file_name,
    build_scope_applied,
    fetch_sec_financials as do_fetch_sec_financials,
    financials_summary,
)
from services.comparative import handle_run_comparative_analysis, handle_set_comparative_inputs
from session_binding import resolve_workspace_session
from store import (
    REQUIRED_DCF_FIELDS,
    build_dcf_inputs_from_bundle,
    cleanup_expired_sessions,
    company_name_from_bundle,
    find_file_by_dedup_key,
    merge_model_inputs,
    save_dcf_model,
    save_file_entry,
    update_file_entry,
    summarize_input_bundle,
)

VIEW_BASE_URL = os.getenv("VIEW_BASE_URL", "http://localhost:5173").rstrip("/")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))

INSTRUCTIONS = """
You help users with financial modeling in a private workspace: DCF valuation, SEC financials,
and peer comparative analysis.

CAPABILITIES:
1. DCF — set_model_inputs + run_dcf
2. SEC filings — fetch_sec_financials (Files panel on dashboard)
3. Peer comparison — set_comparative_inputs + fetch_sec_financials per company + run_comparative_analysis

SEC FETCH — map user words to fetch_sec_financials parameters:
| User says | Parameters |
|-----------|------------|
| "Fetch Apple reports" / latest financials | defaults (max_years=1, include_annual=true, include_quarterly=false) |
| "Apple 2023" / "FY2023 report" | fiscal_years=[2023], include_annual=true, include_quarterly=false |
| "Last 5 years" | max_years=5, include_annual=true; add include_quarterly=true only if user asks quarterly |
| "Quarterly" / "last 4 quarters" | include_annual=false, include_quarterly=true, max_years=1 |
| "Apple 2023 quarterly" | fiscal_years=[2023], include_annual=false, include_quarterly=true |
| Peer comparison (each company) | max_years=1, include_quarterly=false — ONE company per call, sequentially |

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
            "What would you like to do — build a DCF, fetch SEC financials, "
            "or run a peer comparison?"
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

    DCF RULES:
    - Pass ONLY keys the user explicitly gave you in chat. Do not fill missing fields.
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
    - Peer comparison: ONE company per call, max_years=1, include_quarterly=false.
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

    resolved = sec_resolve_ticker(company_name=company_name, ticker=ticker)
    if "error" in resolved:
        return _with_session(sid, resolved)

    sym = resolved["ticker"]
    dedup_key = build_dedup_key(
        sym,
        fiscal_years=fiscal_years,
        max_years=max_years,
        include_annual=include_annual,
        include_quarterly=include_quarterly,
        statements=valid_stmts,
    )

    _touch_session_writes()
    existing = find_file_by_dedup_key(sid, dedup_key)

    try:
        financials = do_fetch_sec_financials(
            company_name=company_name,
            ticker=ticker,
            fiscal_years=fiscal_years,
            max_years=max_years,
            include_annual=include_annual,
            include_quarterly=include_quarterly,
            statements=valid_stmts,
        )
    except ValueError as exc:
        return _with_session(sid, {"error": str(exc)})
    except Exception as exc:
        return _with_session(
            sid,
            {
                "error": f"SEC fetch failed for {sym}: {exc}",
                "hint": "Retry one company at a time; on small EC2 try include_quarterly=false.",
            },
        )

    dcf_suggested = suggest_dcf_inputs(financials)
    dcf_prefilled: dict = {}
    if dcf_suggested:
        summary_bundle = merge_model_inputs(sid, dcf_suggested)
        dcf_prefilled = summary_bundle.get("filled") or {}

    dcf_response = {
        "dcf_prefilled": dcf_prefilled,
        "dcf_still_required": dcf_still_required(dcf_prefilled),
    }

    file_name = build_file_name(
        sym,
        fiscal_years=fiscal_years,
        max_years=max_years,
    )
    scope = build_scope_applied(
        fiscal_years=fiscal_years,
        max_years=max_years,
        include_annual=include_annual,
        include_quarterly=include_quarterly,
        statements=valid_stmts,
        financials=financials,
    )
    summary = financials_summary(financials, scope_applied=scope)

    if existing:
        entry = update_file_entry(
            sid,
            existing["id"],
            {
                "name": file_name,
                "type": "financials",
                "dedup_key": dedup_key,
                "data": financials.model_dump(),
            },
        )
        return _with_session(
            sid,
            {
                **summary,
                **dcf_response,
                "file_id": entry["id"],
                "file_name": entry["name"],
                "deduplicated": True,
                "refreshed": True,
                "message": (
                    f"Refreshed '{entry['name']}' from SEC. "
                    f"FY included: {scope['fiscal_years_included']}. "
                    f"Open {_view_url(sid)} to view."
                ),
            },
        )

    entry = save_file_entry(
        sid,
        {
            "name": file_name,
            "type": "financials",
            "dedup_key": dedup_key,
            "data": financials.model_dump(),
        },
    )
    return _with_session(
        sid,
        {
            **summary,
            **dcf_response,
            "file_id": entry["id"],
            "file_name": entry["name"],
            "deduplicated": False,
            "message": (
                f"Saved '{entry['name']}' to Files. "
                f"FY included: {scope['fiscal_years_included']}; "
                f"quarterly FYs: {scope['quarterly_fiscal_years_included'] or 'none'}. "
                f"Open {_view_url(sid)} to browse."
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

    WORKFLOW (in order):
    1. values.target + values.peers — register tickers
    2. fetch_sec_financials once per company (sequential; max_years=1, include_quarterly=false)
    3. values.link — {{ticker, file_id}} for each company from step 2
    4. run_comparative_analysis when ready=true

    COMPARATIVE RULES:
    - values.target: {{ticker, company_name?}}
    - values.peers: list of {{ticker, company_name?}} (1–10)
    - values.fiscal_year: optional int; omit to auto-pick earliest latest FY across all companies
    - values.link: {{ticker, file_id, company_name?}} after each fetch_sec_financials
    - Do NOT call run_comparative_analysis until ready=true.
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
    Build comparative report when set_comparative_inputs reports ready=true.

    Fetches Finnhub market data (price, market cap) and computes fundamentals + multiples
    from linked SEC files. Saves type=comparative model to dashboard.
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
