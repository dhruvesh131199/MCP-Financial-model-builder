"""Tests for detailed analysis sync on fetch and cache materialization."""

from __future__ import annotations

from unittest.mock import patch

from ingest.normalize import LineItem, StatementPeriod, StatementSlice, FinancialStatements
from services.detailed_analysis_service import (
    save_detailed_analysis_from_cache,
    should_sync_detailed_analysis_on_fetch,
)
from services.statements_store import sync_financials_to_cache
from store import create_session, find_detailed_analysis_by_ticker, load_workspace


def _fin(years: list[int]) -> FinancialStatements:
    annual = [
        StatementPeriod(
            fiscal_year=y,
            fiscal_period="FY",
            period_end=f"{y}-12-31",
            line_items=[
                LineItem(key="revenue", label="Revenue", value=100.0, unit="USD"),
                LineItem(key="cost_of_revenue", label="COGS", value=40.0, unit="USD"),
                LineItem(key="gross_profit", label="GP", value=60.0, unit="USD", source="derived"),
                LineItem(key="operating_income", label="OI", value=20.0, unit="USD"),
                LineItem(key="net_income", label="NI", value=15.0, unit="USD"),
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


def test_should_sync_detailed_analysis_on_fetch():
    assert should_sync_detailed_analysis_on_fetch(
        max_years=5,
        include_annual=True,
        statements=["income", "balance", "cashflow"],
    )
    assert not should_sync_detailed_analysis_on_fetch(
        max_years=1,
        include_annual=True,
        statements=["income", "balance", "cashflow"],
    )
    assert not should_sync_detailed_analysis_on_fetch(
        max_years=5,
        include_annual=True,
        statements=["income"],
    )


def test_save_detailed_analysis_from_cache_creates_model():
    sid = create_session()
    sync_financials_to_cache(sid, _fin([2025, 2024, 2023, 2022, 2021]))

    result = save_detailed_analysis_from_cache(sid, "AAPL", max_years=5)
    assert result is not None
    assert result["periods_count"] == 5

    entry = find_detailed_analysis_by_ticker(sid, "AAPL")
    assert entry is not None
    assert entry["name"] == "AAPL"
    years = [p["fiscal_year"] for p in entry["data"]["periods"]]
    assert years == [2025, 2024, 2023, 2022, 2021]
    assert entry["data"].get("trend_analysis") is not None
    assert len(entry["data"]["trend_analysis"]["rows"]) == 8

    ws = load_workspace(sid)
    assert any(m["type"] == "detailed_analysis" for m in ws["models"])


@patch("services.sec_financials.fetch_edgar_statements")
@patch("services.sec_financials.resolve_ticker")
def test_fetch_5y_populates_detailed_analysis_via_cache(mock_resolve, mock_edgar):
    sid = create_session()
    mock_resolve.return_value = {"ticker": "AAPL", "cik": "1", "entity_name": "Apple Inc."}
    mock_edgar.return_value = _fin([2025, 2024, 2023, 2022, 2021])

    from services.sec_financials import fetch_and_cache_statements

    assert should_sync_detailed_analysis_on_fetch(
        max_years=5,
        include_annual=True,
        statements=["income", "balance", "cashflow"],
    )

    fetch_and_cache_statements(
        sid,
        ticker="AAPL",
        max_years=5,
        statements=["income", "balance", "cashflow"],
    )
    result = save_detailed_analysis_from_cache(sid, "AAPL", max_years=5)
    assert result is not None
    assert find_detailed_analysis_by_ticker(sid, "AAPL") is not None
