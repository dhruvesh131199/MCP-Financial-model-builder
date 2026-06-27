"""Tests that SEC fetch does not auto-persist DCF inputs."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

import store as store_module
from ingest.normalize import FinancialStatements, LineItem, StatementPeriod, StatementSlice
from store import create_session, load_input_bundle

_SERVER_PATH = Path(__file__).resolve().parents[1] / "mcp" / "server.py"
_spec = importlib.util.spec_from_file_location("financial_mcp_server", _SERVER_PATH)
_server = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_server)
_handle_cached_sec_fetch = _server._handle_cached_sec_fetch


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

    with patch.object(_server, "fetch_and_cache_statements") as mock_fetch:
        mock_fetch.return_value = (_fin(), [], True, "f1", "MU")
        result = _handle_cached_sec_fetch(
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
