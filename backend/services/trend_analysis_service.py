"""Trend analysis orchestration for MCP and API."""

from __future__ import annotations

from typing import Any

from engine.trend_analysis import build_trend_table, trend_to_dict
from helper.analysis.schema import snapshot_to_dict
from ingest.detailed_extract import build_detailed_snapshot_from_financials
from services.sec_financials import materialize_ticker_file_view
from store import find_detailed_analysis_by_ticker, save_detailed_analysis_model


def build_trend_from_snapshot(snapshot: Any, *, max_years: int = 5) -> dict[str, Any]:
    return trend_to_dict(build_trend_table(snapshot, max_years=max_years))


def run_trend_analysis_for_session(
    session_id: str,
    ticker: str,
    *,
    max_years: int = 5,
) -> dict[str, Any]:
    sym = ticker.upper()
    financials = materialize_ticker_file_view(session_id, sym)
    if financials is None:
        return {
            "error": (
                f"No cached statements for {sym}. "
                "Run fetch_report(just_financials) or run_detailed_analysis first."
            ),
        }

    snapshot = build_detailed_snapshot_from_financials(
        financials, max_periods=max_years
    )
    if not snapshot.periods:
        return {"error": f"No annual periods in cache for {sym}."}

    trend = build_trend_from_snapshot(snapshot, max_years=max_years)
    existing = find_detailed_analysis_by_ticker(session_id, sym)

    if existing:
        data = dict(existing["data"])
        data["trend_analysis"] = trend
        entry = save_detailed_analysis_model(
            session_id,
            {
                "data": data,
                "source": existing.get("source"),
            },
        )
    else:
        analysis_data = snapshot_to_dict(snapshot)
        analysis_data["trend_analysis"] = trend
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
        "success": True,
        "analysis_id": entry["id"],
        "analysis_name": entry["name"],
        "ticker": sym,
        "periods_count": len(snapshot.periods),
        "trend_row_count": len(trend.get("rows") or []),
    }
