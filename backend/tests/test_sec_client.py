"""Tests for SEC ticker resolution."""

import services.sec_client as sec_client


MOCK_INDEX = [
    {"ticker": "AAPL", "cik": "0000320193", "title": "Apple Inc."},
    {"ticker": "TSLA", "cik": "0001318605", "title": "Tesla, Inc."},
]


def test_resolve_ticker_by_symbol(monkeypatch):
    monkeypatch.setattr(sec_client, "load_ticker_index", lambda: MOCK_INDEX)
    result = sec_client.resolve_ticker(ticker="AAPL")
    assert result["ticker"] == "AAPL"
    assert result["matched_by"] == "ticker"


def test_resolve_ticker_invalid(monkeypatch):
    monkeypatch.setattr(sec_client, "load_ticker_index", lambda: MOCK_INDEX)
    result = sec_client.resolve_ticker(ticker="ZZZZ")
    assert "error" in result


def test_resolve_company_name_apple(monkeypatch):
    monkeypatch.setattr(sec_client, "load_ticker_index", lambda: MOCK_INDEX)
    result = sec_client.resolve_ticker(company_name="apple")
    assert result["ticker"] == "AAPL"
    assert result["matched_by"] == "company_name"


def test_resolve_company_name_tesla(monkeypatch):
    monkeypatch.setattr(sec_client, "load_ticker_index", lambda: MOCK_INDEX)
    result = sec_client.resolve_ticker(company_name="tesla")
    assert result["ticker"] == "TSLA"
