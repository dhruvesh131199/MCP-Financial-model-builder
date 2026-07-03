"""REST API for session-scoped model creation."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from services.dcf_service import create_dcf_draft
from store import create_session, get_model_entry
from tests.test_dcf_service import _mock_financials

client = TestClient(app)


@patch("services.dcf_service.fetch_and_cache_statements")
@patch("services.dcf_service.resolve_ticker")
def test_post_create_dcf_with_ticker(mock_resolve, mock_fetch):
    sid = create_session()
    mock_resolve.return_value = {"ticker": "MU", "entity_name": "Micron", "cik": "1"}
    mock_fetch.return_value = (_mock_financials(), [], True, "f1", "MU")

    res = client.post(
        f"/api/sessions/{sid}/models/dcf",
        json={"name": "My Micron DCF", "ticker": "MU", "projection_years": 3},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["model_name"] == "My Micron DCF"
    assert body["reference_years"] == 5
    assert body["prefilled"]["base_revenue"] is not None

    entry = get_model_entry(sid, body["model_id"])
    assert entry is not None
    assert entry["type"] == "dcf_draft"
    assert len(entry["data"]["inputs"]["revenue_growth"]) == 3


def test_post_create_dcf_without_ticker():
    sid = create_session()
    res = client.post(
        f"/api/sessions/{sid}/models/dcf",
        json={
            "name": "Blank template",
            "projection_years": 5,
            "base_revenue": 1200.0,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["reference_years"] == 0
    assert body["prefilled"]["base_revenue"] == 1200.0

    entry = get_model_entry(sid, body["model_id"])
    assert entry["data"]["inputs"]["base_revenue"] == 1200.0
    assert entry["data"]["reference_history"]["fiscal_years"] == []


@patch("services.dcf_service.fetch_and_cache_statements")
@patch("services.dcf_service.resolve_ticker")
def test_post_create_dcf_base_revenue_override(mock_resolve, mock_fetch):
    sid = create_session()
    mock_resolve.return_value = {"ticker": "MU", "entity_name": "Micron", "cik": "1"}
    mock_fetch.return_value = (_mock_financials(), [], True, "f1", "MU")

    res = client.post(
        f"/api/sessions/{sid}/models/dcf",
        json={
            "name": "Override DCF",
            "ticker": "MU",
            "projection_years": 2,
            "base_revenue": 999.0,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["prefilled"]["base_revenue"] == 999.0

    entry = get_model_entry(sid, body["model_id"])
    assert entry["data"]["inputs"]["base_revenue"] == 999.0


def test_post_create_dcf_invalid_projection_years():
    sid = create_session()
    res = client.post(
        f"/api/sessions/{sid}/models/dcf",
        json={"name": "Bad", "projection_years": 11},
    )
    assert res.status_code == 422


def test_post_create_dcf_session_not_found():
    res = client.post(
        "/api/sessions/not-a-uuid/models/dcf",
        json={"name": "X", "projection_years": 5},
    )
    assert res.status_code == 404


def _resolve_ticker_side_effect(**kwargs):
    sym = (kwargs.get("ticker") or "").upper()
    if sym == "BAD":
        return {"error": "Ticker 'BAD' not found in SEC company list"}
    if sym:
        return {"ticker": sym, "entity_name": sym, "cik": "1", "matched_by": "ticker"}
    return {"error": "Provide company_name or ticker"}


@patch("services.comparative.fetch_market_snapshot")
@patch("services.comparative.fetch_and_cache_statements")
@patch("services.comparative.resolve_ticker")
def test_post_create_comparative_happy(mock_resolve, mock_fetch, mock_market):
    from tests.test_comparative_mcp import _financials
    from store import save_file_entry

    sid = create_session()
    mock_resolve.side_effect = _resolve_ticker_side_effect

    def _fake_fetch(session_id, **kw):
        ticker = kw["ticker"]
        data = _financials(ticker, prior_revenue=8e8)
        entry = save_file_entry(
            session_id,
            {
                "name": ticker,
                "type": "financials",
                "dedup_key": f"dk-{ticker}",
                "data": data,
            },
        )
        return (data, [], True, entry["id"], ticker)

    mock_fetch.side_effect = _fake_fetch
    mock_market.return_value = {"ok": True, "price": 50.0, "market_cap": 1e11}

    res = client.post(
        f"/api/sessions/{sid}/models/comparative",
        json={"target": "KO", "peers": ["PEP"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["model_name"] == "KO vs PEP"
    assert body["model_id"]

    entry = get_model_entry(sid, body["model_id"])
    assert entry is not None
    assert entry["type"] == "comparative"


@patch("services.comparative.resolve_ticker")
def test_post_create_comparative_bad_ticker(mock_resolve):
    sid = create_session()
    mock_resolve.side_effect = _resolve_ticker_side_effect

    res = client.post(
        f"/api/sessions/{sid}/models/comparative",
        json={"target": "BAD", "peers": ["PEP"]},
    )
    assert res.status_code == 400
    assert "not found" in res.json()["detail"].lower()


@patch("services.comparative.fetch_and_cache_statements")
@patch("services.comparative.resolve_ticker")
def test_post_create_comparative_sec_fetch_failure(mock_resolve, mock_fetch):
    sid = create_session()
    mock_resolve.side_effect = _resolve_ticker_side_effect
    mock_fetch.side_effect = ValueError("SEC unavailable")

    res = client.post(
        f"/api/sessions/{sid}/models/comparative",
        json={"target": "KO", "peers": ["PEP"], "name": "My Comps"},
    )
    assert res.status_code == 400
    assert "SEC fetch failed" in res.json()["detail"]


def test_post_create_comparative_too_many_peers():
    sid = create_session()
    res = client.post(
        f"/api/sessions/{sid}/models/comparative",
        json={"target": "KO", "peers": ["A", "B", "C", "D", "E", "F"]},
    )
    assert res.status_code == 422


def test_post_create_comparative_no_peers():
    sid = create_session()
    res = client.post(
        f"/api/sessions/{sid}/models/comparative",
        json={"target": "KO", "peers": []},
    )
    assert res.status_code == 422
