"""Tests for Finnhub market data service."""

from unittest.mock import patch

import pytest

import services.market_data as md


def test_fetch_market_snapshot_success():
    with patch.object(md, "verify_finnhub_config", return_value={"ok": True, "error": None}), patch.object(
        md, "fetch_quote", return_value={"stock_price": 62.1, "previous_close": 61.0}
    ), patch.object(
        md,
        "fetch_profile",
        return_value={
            "company_name": "Coca-Cola",
            "exchange": "NYSE",
            "industry": "Beverages",
            "market_cap_usd": 2680.5 * 1_000_000,
            "shares_outstanding": 4320.0 * 1_000_000,
        },
    ):
        snap = md.fetch_market_snapshot("KO")

    assert snap["stock_price"] == 62.1
    assert snap["market_cap_usd"] == pytest.approx(2680.5 * 1_000_000)
    assert snap["ok"] is True
    assert snap["source"] == "finnhub"


def test_missing_api_key():
    with patch.object(md, "_finnhub_api_key", return_value=""):
        with pytest.raises(ValueError, match="FINNHUB_API_KEY"):
            md._get_json("/quote", {"symbol": "AAPL"})


def test_verify_finnhub_config_missing():
    with patch.object(md, "_finnhub_api_key", return_value=""):
        result = md.verify_finnhub_config()
    assert result["ok"] is False


def test_fetch_snapshot_no_api_key():
    with patch.object(md, "_finnhub_api_key", return_value=""):
        snap = md.fetch_market_snapshot("V")
    assert snap["ok"] is False
    assert "FINNHUB_API_KEY" in snap["errors"][0]


def test_quote_fails_profile_derives_price():
    with patch.object(md, "verify_finnhub_config", return_value={"ok": True, "error": None}), patch.object(
        md, "fetch_quote", side_effect=ValueError("Finnhub HTTP 404")
    ), patch.object(
        md,
        "fetch_profile",
        return_value={
            "market_cap_usd": 100_000_000.0,
            "shares_outstanding": 1_000_000.0,
            "company_name": "Test",
        },
    ):
        snap = md.fetch_market_snapshot("TST")
    assert snap["stock_price"] == pytest.approx(100.0)
    assert snap["ok"] is True


def test_profile_fails_quote_derives_market_cap():
    with patch.object(md, "verify_finnhub_config", return_value={"ok": True, "error": None}), patch.object(
        md, "fetch_quote", return_value={"stock_price": 50.0}
    ), patch.object(md, "fetch_profile", side_effect=ValueError("Finnhub HTTP 500")):
        snap = md.fetch_market_snapshot("TST", sec_shares_outstanding=2_000_000.0)
    assert snap["market_cap_usd"] == pytest.approx(100_000_000.0)
    assert snap["ok"] is True


def test_both_fail():
    with patch.object(md, "verify_finnhub_config", return_value={"ok": True, "error": None}), patch.object(
        md, "fetch_quote", side_effect=ValueError("fail")
    ), patch.object(md, "fetch_profile", side_effect=ValueError("fail")):
        snap = md.fetch_market_snapshot("BAD")
    assert snap["ok"] is False
    assert len(snap["errors"]) == 2


def test_http_429():
    import httpx

    request = httpx.Request("GET", "https://finnhub.io/api/v1/quote")
    with patch.object(md, "_finnhub_api_key", return_value="test-key"), patch(
        "services.market_data.httpx.Client"
    ) as client_cls:
        client = client_cls.return_value.__enter__.return_value
        resp = httpx.Response(429, request=request)

        def _raise():
            raise httpx.HTTPStatusError("429", request=request, response=resp)

        resp.raise_for_status = _raise
        client.get.return_value = resp
        with pytest.raises(ValueError, match="429"):
            md._get_json("/quote", {"symbol": "AAPL"})


def test_lazy_env_after_load_dotenv(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    assert md._finnhub_api_key() == ""
    monkeypatch.setenv("FINNHUB_API_KEY", "late-key")
    assert md._finnhub_api_key() == "late-key"
