"""Tests that fetch_and_cache_statements always syncs Files from cache."""

from __future__ import annotations

from unittest.mock import patch

from ingest.normalize import LineItem, StatementPeriod, StatementSlice, FinancialStatements
from services.sec_financials import fetch_and_cache_statements
from services.statements_store import sync_financials_to_cache
from store import create_session, find_financials_file_for_ticker, load_workspace


def _fin(*, years: list[int], statements: list[str] | None = None) -> FinancialStatements:
    stmts = statements or ["income", "balance", "cashflow"]
    slices: dict[str, StatementSlice] = {}
    for stmt in stmts:
        slices[stmt] = StatementSlice(
            annual=[
                StatementPeriod(
                    fiscal_year=y,
                    fiscal_period="FY",
                    period_end=f"{y}-12-31",
                    line_items=[
                        LineItem(key="revenue", label="Revenue", value=100.0, unit="USD"),
                    ],
                )
                for y in years
            ]
        )
    return FinancialStatements(
        ticker="AAPL",
        cik="1",
        entity_name="Apple Inc.",
        fetched_at="2026-01-01T00:00:00+00:00",
        statements=slices,
        fetch_scope=stmts,
        ingest_source="test",
    )


@patch("services.sec_financials.fetch_edgar_statements")
@patch("services.sec_financials.resolve_ticker")
def test_fetch_income_only_creates_ticker_file(mock_resolve, mock_edgar):
    sid = create_session()
    mock_resolve.return_value = {"ticker": "AAPL", "cik": "1", "entity_name": "Apple Inc."}
    mock_edgar.return_value = _fin(years=[2023], statements=["income"])

    _, _, _, file_id, file_name = fetch_and_cache_statements(
        sid,
        ticker="AAPL",
        fiscal_years=[2023],
        statements=["income"],
    )
    assert file_name == "AAPL"
    assert file_id

    entry = find_financials_file_for_ticker(sid, "AAPL")
    assert entry is not None
    assert entry["id"] == file_id
    assert len(entry["data"]["statements"]["income"]["annual"]) == 1


@patch("services.sec_financials.fetch_edgar_statements")
@patch("services.sec_financials.resolve_ticker")
def test_second_fetch_updates_same_file_id(mock_resolve, mock_edgar):
    sid = create_session()
    mock_resolve.return_value = {"ticker": "AAPL", "cik": "1", "entity_name": "Apple Inc."}
    mock_edgar.return_value = _fin(years=[2023], statements=["income"])

    _, _, _, file_id_1, _ = fetch_and_cache_statements(
        sid,
        ticker="AAPL",
        fiscal_years=[2023],
        statements=["income"],
    )

    mock_edgar.return_value = _fin(years=[2023], statements=["balance"])
    _, _, _, file_id_2, _ = fetch_and_cache_statements(
        sid,
        ticker="AAPL",
        fiscal_years=[2023],
        statements=["balance"],
    )
    assert file_id_1 == file_id_2
    entry = find_financials_file_for_ticker(sid, "AAPL")
    assert "balance" in entry["data"]["statements"]
    assert len(entry["data"]["statements"]["income"]["annual"]) == 1


@patch("services.sec_financials.resolve_ticker")
def test_cache_only_hit_still_upserts_file(mock_resolve):
    sid = create_session()
    mock_resolve.return_value = {"ticker": "AAPL", "cik": "1", "entity_name": "Apple Inc."}
    sync_financials_to_cache(sid, _fin(years=[2023, 2024]))

    assert find_financials_file_for_ticker(sid, "AAPL") is None

    _, gaps, had_fetch, file_id, file_name = fetch_and_cache_statements(
        sid,
        ticker="AAPL",
        max_years=2,
        statements=["income", "balance", "cashflow"],
    )
    assert had_fetch is False
    assert gaps == []
    assert file_name == "AAPL"
    entry = find_financials_file_for_ticker(sid, "AAPL")
    assert entry is not None
    assert entry["id"] == file_id
    assert len(entry["data"]["statements"]["income"]["annual"]) == 2

    ws = load_workspace(sid)
    assert ws is not None
    assert len(ws["files"]) == 1
