"""Shared SEC structured fetch handler (MCP + REST)."""

from __future__ import annotations

import os

from services.sec_client import resolve_ticker as sec_resolve_ticker
from services.sec_financials import (
    build_scope_applied,
    fetch_and_cache_statements,
    financials_summary,
)

VIEW_BASE_URL = os.getenv("VIEW_BASE_URL", "http://localhost:5173").rstrip("/")


def _view_url(session_id: str) -> str:
    return f"{VIEW_BASE_URL}/s/{session_id}"


def handle_cached_sec_fetch(
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

    return {
        **summary,
        "file_id": file_id,
        "file_name": file_name,
        "deduplicated": True,
        "refreshed": bool(had_fetch or gaps_filled),
        "statements_cached": not had_fetch and not gaps_filled,
        "gaps_filled": gaps_filled,
        "scope_applied": scope,
        "message": (
            f"Saved '{file_name}' to Files{cache_note}. "
            f"This fetch scope: FY {scope['fiscal_years_included']}; "
            f"quarterly FYs: {scope['quarterly_fiscal_years_included'] or 'none'}. "
            f"Open {_view_url(sid)} to browse."
        ),
    }
