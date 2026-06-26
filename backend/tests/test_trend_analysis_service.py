"""Tests for trend analysis service."""

from __future__ import annotations

from ingest.normalize import LineItem, StatementPeriod, StatementSlice, FinancialStatements
from services.trend_analysis_service import run_trend_analysis_for_session
from services.detailed_analysis_service import save_detailed_analysis_from_cache
from services.statements_store import sync_financials_to_cache
from store import create_session, find_detailed_analysis_by_ticker


def _fin(years: list[int]) -> FinancialStatements:
    annual = [
        StatementPeriod(
            fiscal_year=y,
            fiscal_period="FY",
            period_end=f"{y}-12-31",
            line_items=[
                LineItem(key="revenue", label="Revenue", value=100.0 * y, unit="USD"),
                LineItem(key="cost_of_revenue", label="COGS", value=40.0, unit="USD"),
                LineItem(
                    key="gross_profit",
                    label="GP",
                    value=60.0,
                    unit="USD",
                    source="derived",
                ),
                LineItem(key="operating_income", label="OI", value=20.0, unit="USD"),
                LineItem(key="net_income", label="NI", value=15.0, unit="USD"),
                LineItem(key="eps_diluted", label="EPS", value=1.5, unit="USD/shares"),
            ],
        )
        for y in years
    ]
    return FinancialStatements(
        ticker="AAPL",
        cik="1",
        entity_name="Apple Inc.",
        fetched_at="2026-01-01T00:00:00+00:00",
        statements={
            "income": StatementSlice(annual=annual),
            "balance": StatementSlice(annual=annual),
            "cashflow": StatementSlice(annual=annual),
        },
        ingest_source="test",
    )


def test_save_detailed_analysis_includes_trend_analysis():
    sid = create_session()
    sync_financials_to_cache(sid, _fin([2025, 2024, 2023]))

    save_detailed_analysis_from_cache(sid, "AAPL", max_years=3)
    entry = find_detailed_analysis_by_ticker(sid, "AAPL")
    assert entry is not None
    trend = entry["data"].get("trend_analysis")
    assert trend is not None
    assert trend["fiscal_years"] == [2025, 2024, 2023]
    assert len(trend["rows"]) == 8
    growth = next(r for r in trend["rows"] if r["key"] == "revenue_growth_yoy")
    assert growth["highlight"] is True


def test_run_trend_analysis_upserts_existing_model():
    sid = create_session()
    sync_financials_to_cache(sid, _fin([2025, 2024]))
    save_detailed_analysis_from_cache(sid, "AAPL", max_years=2)

    result = run_trend_analysis_for_session(sid, "AAPL", max_years=2)
    assert result["success"] is True
    assert result["trend_row_count"] == 8

    entry = find_detailed_analysis_by_ticker(sid, "AAPL")
    assert entry["data"].get("trend_analysis") is not None
