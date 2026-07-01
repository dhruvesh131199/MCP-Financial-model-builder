"""Tests for comparative MCP handlers."""

from unittest.mock import patch

import pytest

import store as store_module
from services.comparative import handle_run_comparative_analysis, handle_set_comparative_inputs
from store import create_session, save_file_entry


def _financials(ticker: str, fy: int = 2024, *, prior_revenue: float | None = None) -> dict:
    annual = [
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
    ]
    if prior_revenue is not None:
        annual.append(
            {
                "fiscal_year": fy - 1,
                "fiscal_period": "FY",
                "form": "10-K",
                "line_items": [
                    {"key": "revenue", "label": "Revenue", "value": prior_revenue, "unit": "USD"},
                    {"key": "net_income", "label": "NI", "value": 9e7, "unit": "USD"},
                ],
            }
        )
    return {
        "ticker": ticker,
        "cik": "0000000001",
        "entity_name": ticker,
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "statements": {
            "income": {"annual": annual, "quarterly": []},
            "balance": {"annual": [], "quarterly": []},
            "cashflow": {"annual": [], "quarterly": []},
        },
    }


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)


@pytest.fixture
def block_comparative_sec_fetch():
    with patch(
        "services.comparative.fetch_and_cache_statements",
        side_effect=ValueError("SEC fetch blocked in unit test"),
    ):
        yield


def test_set_comparative_inputs_stages():
    sid = create_session()
    result = handle_set_comparative_inputs(
        sid,
        {"target": {"ticker": "KO"}, "peers": [{"ticker": "PEP"}]},
    )
    assert result["ready"] is False
    assert "fetch_report" in result["next_step"] or "run_comparative_analysis" in result["next_step"]


def test_run_not_ready_without_sec_files(block_comparative_sec_fetch):
    sid = create_session()
    handle_set_comparative_inputs(sid, {"target": {"ticker": "KO"}, "peers": [{"ticker": "PEP"}]})
    result = handle_run_comparative_analysis(sid)
    assert result["success"] is False


def test_run_happy_path(block_comparative_sec_fetch):
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


def test_run_per_company_fiscal_year(block_comparative_sec_fetch):
    sid = create_session()
    ko = save_file_entry(
        sid,
        {"name": "KO", "type": "financials", "dedup_key": "k3", "data": _financials("KO", fy=2025)},
    )
    pep = save_file_entry(
        sid,
        {"name": "PEP", "type": "financials", "dedup_key": "p3", "data": _financials("PEP", fy=2024)},
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
    from store import _load_model_entries, _session_dir

    models = _load_model_entries(_session_dir(sid))
    report = next(m for m in models if m["type"] == "comparative")
    by_ticker = {c["ticker"]: c for c in report["data"]["companies"]}
    assert by_ticker["KO"]["fundamentals"]["fiscal_year"] == 2025
    assert by_ticker["PEP"]["fundamentals"]["fiscal_year"] == 2024
    assert by_ticker["PEP"]["fundamentals"]["revenue"] == 1e9


def test_run_comparative_revenue_growth_with_two_years():
    sid = create_session()
    ko = save_file_entry(
        sid,
        {
            "name": "KO",
            "type": "financials",
            "dedup_key": "k4",
            "data": _financials("KO", fy=2024, prior_revenue=8e8),
        },
    )
    pep = save_file_entry(
        sid,
        {
            "name": "PEP",
            "type": "financials",
            "dedup_key": "p4",
            "data": _financials("PEP", fy=2024, prior_revenue=9e8),
        },
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
    from store import _load_model_entries, _session_dir

    report = next(m for m in _load_model_entries(_session_dir(sid)) if m["type"] == "comparative")
    ko_row = next(c for c in report["data"]["companies"] if c["ticker"] == "KO")
    assert ko_row["fundamentals"]["revenue_growth_yoy"] == pytest.approx(0.25)


def test_ensure_comparative_fetches_two_year_gaps():
    sid = create_session()
    from services.comparative import COMPARATIVE_SEC_MAX_YEARS, comparative_fetch_gaps, ensure_comparative_sec_files
    from services.statements_store import sync_financials_to_cache
    from ingest.normalize import FinancialStatements, LineItem, StatementPeriod, StatementSlice

    fin = FinancialStatements(
        ticker="MU",
        cik="1",
        entity_name="Micron",
        fetched_at="2026-01-01T00:00:00+00:00",
        statements={
            "income": StatementSlice(
                annual=[
                    StatementPeriod(
                        fiscal_year=2025,
                        fiscal_period="FY",
                        period_end="2025-08-31",
                        line_items=[
                            LineItem(key="revenue", label="R", value=1.0, unit="USD"),
                        ],
                    )
                ]
            ),
            "balance": StatementSlice(annual=[]),
            "cashflow": StatementSlice(annual=[]),
        },
        ingest_source="test",
    )
    sync_financials_to_cache(sid, fin)
    assert comparative_fetch_gaps(sid, "MU")
    assert COMPARATIVE_SEC_MAX_YEARS == 2

    with patch("services.comparative.fetch_and_cache_statements") as mock_fetch:
        mock_fetch.return_value = (fin, [], False, "f1", "MU")
        handle_set_comparative_inputs(
            sid,
            {"target": {"ticker": "MU"}, "peers": [{"ticker": "NVDA"}]},
        )
        ensure_comparative_sec_files(sid)

    mock_fetch.assert_called()
    assert mock_fetch.call_args.kwargs.get("max_years") == 2


def test_finnhub_failure_still_saves(block_comparative_sec_fetch):
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
