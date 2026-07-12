"""Tests for run_detailed_analysis orchestration."""

from __future__ import annotations

from unittest.mock import patch

from ingest.normalize import LineItem, StatementPeriod, StatementSlice, FinancialStatements
from services.detailed_analysis_service import run_detailed_analysis_for_session, save_detailed_analysis_from_cache
from services.statements_store import sync_financials_to_cache
from store import create_session, _session_dir, _load_model_entries


def _fin() -> FinancialStatements:
    annual = [
        StatementPeriod(
            fiscal_year=2025,
            fiscal_period="FY",
            period_end="2025-12-31",
            line_items=[
                LineItem(key="revenue", label="Revenue", value=100.0, unit="USD"),
                LineItem(key="cost_of_revenue", label="COGS", value=40.0, unit="USD"),
                LineItem(key="gross_profit", label="GP", value=60.0, unit="USD", source="derived"),
                LineItem(key="operating_income", label="OI", value=20.0, unit="USD"),
                LineItem(key="net_income", label="NI", value=15.0, unit="USD"),
            ],
        )
    ]
    return FinancialStatements(
        ticker="TEST",
        cik="1",
        entity_name="Test Co",
        fetched_at="2026-01-01T00:00:00+00:00",
        statements={
            "income": StatementSlice(annual=annual),
            "balance": StatementSlice(annual=annual),
            "cashflow": StatementSlice(annual=annual),
        },
        ingest_source="test",
    )


@patch("services.detailed_analysis_service.save_detailed_analysis_from_cache")
@patch("services.detailed_analysis_service.fetch_and_cache_statements")
@patch("services.detailed_analysis_service.resolve_ticker")
def test_run_detailed_analysis_saves_model(mock_resolve, mock_fetch, mock_save):
    sid = create_session()
    mock_resolve.return_value = {"ticker": "TEST", "cik": "1", "entity_name": "Test Co"}
    fin = _fin()
    mock_fetch.return_value = (fin, [], False, "file-1", "TEST")
    mock_save.return_value = {
        "analysis_id": "a1",
        "analysis_name": "TEST",
        "periods_count": 1,
        "integrity_checks": [],
        "is_bank_style": False,
    }

    result = run_detailed_analysis_for_session(sid, ticker="TEST", max_years=1)
    assert result["success"] is True
    assert result["periods_count"] == 1
    assert result["file_id"] == "file-1"
    assert result["file_name"] == "TEST"
    assert len(result["narrative_playbook"]) == 4
    assert len(result["next_actions"]) == 5
    assert "full_report" in result["next_actions"][0]
    mock_save.assert_called_once_with(sid, "TEST", max_years=1)


@patch("services.detailed_analysis_service.save_detailed_analysis_from_cache")
@patch("services.detailed_analysis_service.fetch_and_cache_statements")
@patch("services.detailed_analysis_service.resolve_ticker")
def test_run_detailed_analysis_reuses_analysis_id(mock_resolve, mock_fetch, mock_save):
    sid = create_session()
    mock_resolve.return_value = {"ticker": "TEST", "cik": "1", "entity_name": "Test Co"}
    fin = _fin()
    mock_fetch.return_value = (fin, [], False, "file-1", "TEST")
    mock_save.return_value = {
        "analysis_id": "a1",
        "analysis_name": "TEST",
        "periods_count": 1,
        "integrity_checks": [],
        "is_bank_style": False,
    }

    first = run_detailed_analysis_for_session(sid, ticker="TEST", max_years=1)
    second = run_detailed_analysis_for_session(sid, ticker="TEST", max_years=1)
    assert first["analysis_id"] == second["analysis_id"]


@patch("services.detailed_analysis_service.save_detailed_analysis_from_cache")
@patch("services.detailed_analysis_service.fetch_and_cache_statements")
@patch("services.detailed_analysis_service.resolve_ticker")
def test_run_detailed_analysis_integration_saves_model(mock_resolve, mock_fetch, mock_save):
    sid = create_session()
    mock_resolve.return_value = {"ticker": "TEST", "cik": "1", "entity_name": "Test Co"}
    fin = _fin()
    sync_financials_to_cache(sid, fin)

    def _save(session_id, ticker, *, max_years=5):
        return save_detailed_analysis_from_cache(session_id, ticker, max_years=max_years)

    mock_fetch.return_value = (fin, [], False, "file-1", "TEST")
    mock_save.side_effect = _save

    result = run_detailed_analysis_for_session(sid, ticker="TEST", max_years=1)
    assert result["success"] is True
    models = _load_model_entries(_session_dir(sid))
    assert any(m["type"] == "detailed_analysis" for m in models)
