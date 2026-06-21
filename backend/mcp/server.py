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
from mcp.server.fastmcp import Context, FastMCP

from engine.dcf import compute_dcf
from ingest.normalize import FinancialStatements
from services.sec_client import resolve_ticker as sec_resolve_ticker
from services.sec_financials import (
    build_dedup_key,
    build_file_name,
    fetch_sec_financials as do_fetch_sec_financials,
    financials_summary,
)
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
    summarize_input_bundle,
)

load_dotenv(BACKEND_ROOT / ".env")

VIEW_BASE_URL = os.getenv("VIEW_BASE_URL", "http://localhost:5173").rstrip("/")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))

INSTRUCTIONS = """
You help users build DCF (Discounted Cash Flow) valuation models and fetch SEC financials.

MANDATORY WORKFLOW — follow in order:
1. start_session() — ALWAYS call this first for any workspace task (DCF or SEC fetch).
   Immediately share the view_url with the user.
2. For DCF: ask for missing assumptions → set_model_inputs(values={{...}}) → run_dcf() when ready=true.
3. For SEC financials: call fetch_sec_financials when the user asks for filings, financials,
   or company reports. Use company_name (e.g. "Apple") or ticker (e.g. "AAPL") from the user's words.
   Optional resolve_ticker when you need to confirm a symbol before fetching.

SEC FETCH RULES:
- fetch_sec_financials is independent of DCF — no DCF inputs required.
- fiscal_years=[2023] for a specific year; omit and use max_years=5 for "last 5 years".
- include_annual / include_quarterly default true; set false only if user asks for one period type.
- statements can filter to income, balance, or cashflow subsets.
- Never invent tickers — resolve from what the user said.

DCF RULES:
- set_model_inputs — ONLY include fields the user explicitly stated. Never guess defaults.
- NEVER call run_dcf until set_model_inputs reports ready=true.
- NEVER build a DCF in prose or do arithmetic yourself — use tools only.

CRITICAL:
- After EVERY tool call, show the user their view_url dashboard link.
- NEVER invent numbers for DCF (no default WACC, tax rate, growth, margins, etc.).

Required DCF fields: """ + ", ".join(REQUIRED_DCF_FIELDS) + """
Optional DCF: net_debt, shares_outstanding, company_name
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
    REQUIRED first step for any new DCF build. Creates or reuses this chat's workspace.
    Always call this before collecting inputs. Returns view_url — share it with the user
    immediately so they can open their private dashboard.
    """
    session_id = resolve_workspace_session(ctx)
    _touch_session_writes()
    url = _view_url(session_id)
    return {
        "session_id": session_id,
        "view_url": url,
        "message": (
            f"Workspace ready. Open your dashboard: {url} "
            "Next: ask the user for DCF assumptions, then call set_model_inputs "
            "with ONLY values they stated."
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

    RULES:
    - Pass ONLY keys the user explicitly gave you in chat. Do not fill missing fields.
    - Allowed keys: base_revenue, revenue_growth, ebitda_margin, tax_rate, capex_pct,
      nwc_pct, wacc, terminal_growth, projection_years, net_debt, shares_outstanding,
      company_name
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
    max_years: int = 5,
    include_annual: bool = True,
    include_quarterly: bool = True,
    statements: list[str] | None = None,
    session_id: str | None = None,
) -> dict:
    """
    Fetch official SEC financial statements for a US public company and save to the
    session Files panel on the dashboard.

    Provide company_name (e.g. "Apple") and/or ticker (e.g. "AAPL").
    fiscal_years=[2023] for a specific year only; omit for last max_years (default 5).
    include_annual / include_quarterly control which period types are stored.
    statements optional: income, balance, cashflow (default all three).
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
    if existing:
        summary = financials_summary(
            FinancialStatements.model_validate(existing["data"])
        )
        return _with_session(
            sid,
            {
                **summary,
                "file_id": existing["id"],
                "file_name": existing["name"],
                "deduplicated": True,
                "message": (
                    f"Financials already in Files panel as '{existing['name']}'. "
                    f"Open {_view_url(sid)} to view."
                ),
            },
        )

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

    file_name = build_file_name(
        sym,
        fiscal_years=fiscal_years,
        max_years=max_years,
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
    summary = financials_summary(financials)
    return _with_session(
        sid,
        {
            **summary,
            "file_id": entry["id"],
            "file_name": entry["name"],
            "deduplicated": False,
            "message": (
                f"Saved '{entry['name']}' to Files panel. "
                f"Open {_view_url(sid)} to browse statements."
            ),
        },
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
