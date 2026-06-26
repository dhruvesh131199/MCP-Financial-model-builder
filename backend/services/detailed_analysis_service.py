"""Detailed analysis orchestration for MCP and API."""

from __future__ import annotations

from typing import Any

from homework.detailed_analysis.schema import snapshot_to_dict
from ingest.detailed_extract import build_detailed_snapshot_from_financials
from services.sec_financials import fetch_and_cache_statements, materialize_ticker_file_view
from services.statements_store import compute_fetch_gaps, get_cached_periods_summary
from services.sec_client import resolve_ticker
from store import save_detailed_analysis_model

ALL_STATEMENTS = frozenset({"income", "balance", "cashflow"})


def save_detailed_analysis_from_cache(
    session_id: str,
    ticker: str,
    *,
    max_years: int = 5,
) -> dict[str, Any] | None:
    """Build curated detailed analysis from full cache and upsert dashboard model."""
    sym = ticker.upper()
    financials = materialize_ticker_file_view(session_id, sym)
    if financials is None:
        return None

    snapshot = build_detailed_snapshot_from_financials(
        financials, max_periods=max_years
    )
    if not snapshot.periods:
        return None

    analysis_data = snapshot_to_dict(snapshot)
    entry = save_detailed_analysis_model(
        session_id,
        {
            "data": analysis_data,
            "source": {
                "ticker": sym,
                "statements_ref": f"inputs/statements.json#{sym}",
            },
        },
    )
    return {
        "analysis_id": entry["id"],
        "analysis_name": entry["name"],
        "periods_count": len(analysis_data.get("periods") or []),
        "integrity_checks": analysis_data.get("integrity_checks") or [],
        "is_bank_style": analysis_data.get("is_bank_style", False),
    }


def should_sync_detailed_analysis_on_fetch(
    *,
    max_years: int,
    include_annual: bool,
    statements: list[str],
) -> bool:
    """Full multi-year annual fetch → populate Detailed Analysis sidebar too."""
    if max_years < 5 or not include_annual:
        return False
    return ALL_STATEMENTS.issubset(set(statements))


def run_detailed_analysis_for_session(
    session_id: str,
    *,
    company_name: str | None = None,
    ticker: str | None = None,
    fiscal_years: list[int] | None = None,
    max_years: int = 5,
) -> dict[str, Any]:
    resolved = resolve_ticker(company_name=company_name, ticker=ticker)
    if "error" in resolved:
        return {"error": resolved["error"]}

    sym = resolved["ticker"]
    gaps_before = compute_fetch_gaps(
        session_id,
        sym,
        fiscal_years=fiscal_years,
        max_years=max_years,
        include_annual=True,
        include_quarterly=False,
        statements=["income", "balance", "cashflow"],
    )

    financials, gaps_filled, had_fetch, file_id, file_name = fetch_and_cache_statements(
        session_id,
        company_name=company_name,
        ticker=ticker,
        fiscal_years=fiscal_years,
        max_years=max_years,
        include_annual=True,
        include_quarterly=False,
        statements=["income", "balance", "cashflow"],
    )

    analysis = save_detailed_analysis_from_cache(
        session_id, sym, max_years=max_years
    )
    if analysis is None:
        return {
            "error": (
                f"Could not build Detailed Analysis for {sym} — "
                "no annual statement periods in cache after fetch."
            ),
        }

    entry = {"id": analysis["analysis_id"], "name": analysis["analysis_name"]}

    cache_summary = get_cached_periods_summary(session_id, sym)
    gaps_after = compute_fetch_gaps(
        session_id,
        sym,
        fiscal_years=fiscal_years,
        max_years=max_years,
        include_annual=True,
        include_quarterly=False,
        statements=["income", "balance", "cashflow"],
    )

    return {
        "success": True,
        "analysis_id": entry["id"],
        "analysis_name": entry["name"],
        "file_id": file_id,
        "file_name": file_name,
        "ticker": sym,
        "entity_name": financials.entity_name,
        "periods_count": analysis["periods_count"],
        "integrity_checks": analysis["integrity_checks"],
        "is_bank_style": analysis["is_bank_style"],
        "statements_cached": not had_fetch and len(gaps_before) == 0,
        "gaps_filled": gaps_filled,
        "cache_summary": {
            **cache_summary,
            "still_missing": [
                {"period_key": g.period_key, "statement": g.statement}
                for g in gaps_after
            ],
        },
    }
