"""Tests for comparative MCP handlers."""

from unittest.mock import patch

import pytest

import store as store_module
from services.comparative import handle_run_comparative_analysis, handle_set_comparative_inputs
from store import create_session, save_file_entry


def _financials(ticker: str, fy: int = 2024) -> dict:
    return {
        "ticker": ticker,
        "cik": "0000000001",
        "entity_name": ticker,
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "statements": {
            "income": {
                "annual": [
                    {
                        "fiscal_year": fy,
                        "fiscal_period": "FY",
                        "form": "10-K",
                        "line_items": [
                            {"key": "revenue", "label": "Revenue", "value": 1e9, "unit": "USD"},
                            {"key": "net_income", "label": "NI", "value": 1e8, "unit": "USD"},
                            {"key": "stockholders_equity", "label": "Eq", "value": 5e8, "unit": "USD"},
                            {"key": "shares_outstanding", "label": "Sh", "value": 1e9, "unit": "USD"},
                        ],
                    }
                ],
                "quarterly": [],
            },
            "balance": {"annual": [], "quarterly": []},
            "cashflow": {"annual": [], "quarterly": []},
        },
    }


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)


def test_set_comparative_inputs_stages():
    sid = create_session()
    result = handle_set_comparative_inputs(
        sid,
        {"target": {"ticker": "KO"}, "peers": [{"ticker": "PEP"}]},
    )
    assert result["ready"] is False
    assert "fetch_sec_financials" in result["next_step"]


def test_run_not_ready():
    sid = create_session()
    handle_set_comparative_inputs(sid, {"target": {"ticker": "KO"}, "peers": [{"ticker": "PEP"}]})
    result = handle_run_comparative_analysis(sid)
    assert result["success"] is False


def test_run_happy_path():
    sid = create_session()
    ko = save_file_entry(
        sid,
        {"name": "KO", "type": "financials", "dedup_key": "k1", "data": _financials("KO")},
    )
    pep = save_file_entry(
        sid,
        {"name": "PEP", "type": "financials", "dedup_key": "p1", "data": _financials("PEP")},
    )
    handle_set_comparative_inputs(
        sid,
        {"target": {"ticker": "KO"}, "peers": [{"ticker": "PEP"}]},
    )
    handle_set_comparative_inputs(sid, {"link": {"ticker": "KO", "file_id": ko["id"]}})
    handle_set_comparative_inputs(sid, {"link": {"ticker": "PEP", "file_id": pep["id"]}})

    mock_market = {
        "ticker": "X",
        "stock_price": 50.0,
        "market_cap_usd": 5e10,
        "ok": True,
        "as_of": "2026-01-01",
        "source": "finnhub",
        "errors": [],
    }
    with patch("services.comparative.fetch_market_snapshot", return_value=mock_market):
        result = handle_run_comparative_analysis(sid)

    assert result["success"] is True
    assert result["fiscal_year_used"] == 2024
    assert result["model_id"]


def test_finnhub_failure_still_saves():
    sid = create_session()
    ko = save_file_entry(
        sid,
        {"name": "KO", "type": "financials", "dedup_key": "k2", "data": _financials("KO")},
    )
    pep = save_file_entry(
        sid,
        {"name": "PEP", "type": "financials", "dedup_key": "p2", "data": _financials("PEP")},
    )
    handle_set_comparative_inputs(
        sid,
        {"target": {"ticker": "KO"}, "peers": [{"ticker": "PEP"}]},
    )
    handle_set_comparative_inputs(sid, {"link": {"ticker": "KO", "file_id": ko["id"]}})
    handle_set_comparative_inputs(sid, {"link": {"ticker": "PEP", "file_id": pep["id"]}})

    def _market(ticker, **kwargs):
        if ticker == "PEP":
            return {"ticker": "PEP", "ok": False, "errors": ["fail"]}
        return {
            "ticker": ticker,
            "stock_price": 50.0,
            "market_cap_usd": 5e10,
            "ok": True,
            "as_of": "2026-01-01",
            "source": "finnhub",
            "errors": [],
        }

    with patch("services.comparative.fetch_market_snapshot", side_effect=_market):
        result = handle_run_comparative_analysis(sid)

    assert result["success"] is True
    assert "PEP" in result["market_data_errors"]
