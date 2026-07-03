"""Session-scoped financials fetch REST API tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import store as store_module
from api.main import app
from store import create_session, list_financials_fetch_log

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)


def test_financials_fetch_404_unknown_session():
    res = client.post(
        "/api/sessions/not-a-uuid/financials/fetch",
        json={"tickers": ["AAPL"]},
    )
    assert res.status_code == 404


def test_financials_fetch_400_empty_tickers():
    sid = create_session()
    res = client.post(
        f"/api/sessions/{sid}/financials/fetch",
        json={"tickers": ["  "]},
    )
    assert res.status_code == 422 or res.status_code == 400


@patch("services.financials_fetch_service.run_session_financials_fetch")
def test_financials_fetch_success_and_log(mock_fetch):
    sid = create_session()
    mock_fetch.return_value = {
        "success_count": 2,
        "total_count": 2,
        "results": [
            {"ticker": "AAPL", "success": True, "file_id": "f1"},
            {"ticker": "NVDA", "success": True, "file_id": "f2"},
        ],
        "errors": [],
        "message": "Fetched 2/2",
    }

    res = client.post(
        f"/api/sessions/{sid}/financials/fetch",
        json={"tickers": ["AAPL", "NVDA"], "max_years": 5},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert body["success_count"] == 2
    assert body["max_years"] == 5
    assert body["years"] is None

    mock_fetch.assert_called_once_with(
        sid,
        tickers=["AAPL", "NVDA"],
        years=None,
        max_years=5,
    )

    log = list_financials_fetch_log(sid)
    assert len(log) == 1
    assert log[0]["source"] == "rest"
    assert log[0]["status"] == "success"
    assert log[0]["tickers"] == ["AAPL", "NVDA"]


@patch("services.financials_fetch_service.run_session_financials_fetch")
def test_financials_fetch_specific_years_ignores_max_years(mock_fetch):
    sid = create_session()
    mock_fetch.return_value = {
        "success_count": 1,
        "total_count": 1,
        "results": [{"ticker": "AAPL", "success": True, "file_id": "f1"}],
        "errors": [],
    }

    res = client.post(
        f"/api/sessions/{sid}/financials/fetch",
        json={"tickers": ["AAPL"], "years": [2023, 2024], "max_years": 5},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["years"] == [2023, 2024]
    assert body["max_years"] is None

    mock_fetch.assert_called_once_with(
        sid,
        tickers=["AAPL"],
        years=[2023, 2024],
        max_years=1,
    )


@patch("services.financials_fetch_service.run_session_financials_fetch")
def test_financials_fetch_partial_status(mock_fetch):
    sid = create_session()
    mock_fetch.return_value = {
        "success_count": 1,
        "total_count": 2,
        "results": [
            {"ticker": "AAPL", "success": True, "file_id": "f1"},
            {"ticker": "BAD", "success": False, "error": "Unknown ticker"},
        ],
        "errors": ["BAD: Unknown ticker"],
    }

    res = client.post(
        f"/api/sessions/{sid}/financials/fetch",
        json={"tickers": ["AAPL", "BAD"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "partial"

    log = list_financials_fetch_log(sid)
    assert log[0]["status"] == "partial"


@patch("services.financials_fetch_service.run_session_financials_fetch")
def test_financials_fetch_default_latest(mock_fetch):
    sid = create_session()
    mock_fetch.return_value = {
        "success_count": 1,
        "total_count": 1,
        "results": [{"ticker": "AAPL", "success": True, "file_id": "f1"}],
        "errors": [],
    }

    res = client.post(
        f"/api/sessions/{sid}/financials/fetch",
        json={"tickers": ["AAPL"]},
    )
    assert res.status_code == 200

    mock_fetch.assert_called_once_with(
        sid,
        tickers=["AAPL"],
        years=None,
        max_years=1,
    )
