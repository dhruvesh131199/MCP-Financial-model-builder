"""Tests for hierarchical statements cache."""

from __future__ import annotations

from ingest.normalize import LineItem, StatementPeriod, StatementSlice, FinancialStatements
from services.statements_store import (
    cache_has_quarterly,
    compute_fetch_gaps,
    has_period,
    has_statement,
    has_ticker,
    materialize_financial_statements,
    merge_period_statement,
    sync_financials_to_cache,
)
from store import create_session


def _sample_financials(ticker: str = "AAPL", years: list[int] | None = None) -> FinancialStatements:
    years = years or [2025]
    income_annual = [
        StatementPeriod(
            fiscal_year=y,
            fiscal_period="FY",
            period_end=f"{y}-09-30",
            line_items=[
                LineItem(key="revenue", label="Revenue", value=100.0 * y, unit="USD"),
                LineItem(key="net_income", label="Net Income", value=10.0 * y, unit="USD"),
            ],
        )
        for y in years
    ]
    balance_annual = [
        StatementPeriod(
            fiscal_year=y,
            fiscal_period="FY",
            period_end=f"{y}-09-30",
            line_items=[
                LineItem(key="total_assets", label="Total Assets", value=200.0 * y, unit="USD"),
            ],
        )
        for y in years
    ]
    return FinancialStatements(
        ticker=ticker,
        cik="0000320193",
        entity_name="Apple Inc.",
        fetched_at="2026-01-01T00:00:00+00:00",
        statements={
            "income": StatementSlice(annual=income_annual),
            "balance": StatementSlice(annual=balance_annual),
            "cashflow": StatementSlice(),
        },
        fetch_scope=["income", "balance"],
        ingest_source="test",
    )


def test_merge_and_has_hierarchy():
    sid = create_session()
    merge_period_statement(
        sid,
        "AAPL",
        period_meta={"fiscal_year": 2025, "fiscal_period": "FY", "period_end": "2025-09-30"},
        statement_type="income",
        line_items=[LineItem(key="revenue", label="Revenue", value=1.0, unit="USD")],
        fetch_meta={"fetched_at": "t1", "ingest_source": "test"},
        ticker_meta={"cik": "1", "entity_name": "Apple"},
    )
    assert has_ticker(sid, "AAPL")
    assert has_period(sid, "AAPL", "FY2025")
    assert has_statement(sid, "AAPL", "FY2025", "income")
    assert not has_statement(sid, "AAPL", "FY2025", "balance")


def test_sync_and_incremental_gaps():
    sid = create_session()
    fin = _sample_financials(years=[2025])
    sync_financials_to_cache(sid, fin, statements_written=["income", "balance"])

    gaps = compute_fetch_gaps(
        sid,
        "AAPL",
        max_years=2,
        include_annual=True,
        statements=["income", "balance", "cashflow"],
    )
    period_keys = {g.period_key for g in gaps}
    statements = {g.statement for g in gaps}
    assert "FY2024" in period_keys or any(g.fiscal_year == 2024 for g in gaps)
    assert "cashflow" in statements

    # Add FY2024 income only
    merge_period_statement(
        sid,
        "AAPL",
        period_meta={"fiscal_year": 2024, "fiscal_period": "FY", "period_end": "2024-09-30"},
        statement_type="income",
        line_items=[LineItem(key="revenue", label="Revenue", value=99.0, unit="USD")],
        fetch_meta={"fetched_at": "t2", "ingest_source": "test"},
    )
    assert has_statement(sid, "AAPL", "FY2024", "income")
    assert not has_statement(sid, "AAPL", "FY2024", "balance")


def test_materialize_financial_statements():
    sid = create_session()
    fin = _sample_financials(years=[2025, 2024])
    sync_financials_to_cache(sid, fin)

    out = materialize_financial_statements(sid, "AAPL", max_years=2, statements=["income"])
    assert out is not None
    assert out.ticker == "AAPL"
    assert len(out.statements["income"].annual) == 2


def test_cache_has_quarterly():
    sid = create_session()
    assert cache_has_quarterly(sid, "AAPL") is False
    merge_period_statement(
        sid,
        "AAPL",
        period_meta={"fiscal_year": 2025, "fiscal_period": "Q1", "period_end": "2025-03-31"},
        statement_type="income",
        line_items=[LineItem(key="revenue", label="Revenue", value=1.0, unit="USD")],
        fetch_meta={"fetched_at": "t1", "ingest_source": "test"},
    )
    assert cache_has_quarterly(sid, "AAPL") is True
