"""Tests that SEC fetch does not auto-persist DCF inputs."""

from unittest.mock import patch

import store as store_module
from ingest.normalize import FinancialStatements, LineItem, StatementPeriod, StatementSlice
from services.sec_fetch_handler import handle_cached_sec_fetch
from store import create_session, load_input_bundle


def _fin() -> FinancialStatements:
    annual = [
        StatementPeriod(
            fiscal_year=2025,
            fiscal_period="FY",
            period_end="2025-12-31",
            line_items=[
                LineItem(key="revenue", label="Revenue", value=1e9, unit="USD"),
                LineItem(key="operating_income", label="OI", value=2e8, unit="USD"),
                LineItem(key="net_income", label="NI", value=1.5e8, unit="USD"),
            ],
        )
    ]
    return FinancialStatements(
        ticker="MU",
        cik="1",
        entity_name="Micron",
        fetched_at="2026-01-01T00:00:00+00:00",
        statements={
            "income": StatementSlice(annual=annual),
            "balance": StatementSlice(annual=annual),
            "cashflow": StatementSlice(annual=annual),
        },
        ingest_source="test",
    )


def test_sec_fetch_returns_dcf_suggestions_without_persisting(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()

    with patch("services.sec_fetch_handler.fetch_and_cache_statements") as mock_fetch:
        mock_fetch.return_value = (_fin(), [], True, "f1", "MU")
        result = handle_cached_sec_fetch(
            sid,
            company_name=None,
            ticker="MU",
            fiscal_years=None,
            max_years=1,
            include_annual=True,
            include_quarterly=False,
            statements=["income", "balance", "cashflow"],
        )

    assert "dcf_suggestions" in result
    assert result["dcf_suggestions"].get("base_revenue") is not None
    assert "dcf_prefilled" not in result
    bundle = load_input_bundle(sid)
    assert bundle.get("values") == {}
