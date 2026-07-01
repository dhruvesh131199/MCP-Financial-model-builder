"""Tests for the unified fetch_report MCP tool orchestrator."""

from __future__ import annotations

from unittest.mock import patch

import sys
import os
import importlib.util

# Add the parent directory to sys.path so we can import from mcp directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

# We need to import the local mcp directory, not the installed mcp package
# Let's just use the absolute path to import it directly
import types

# Create a fake module to avoid the import error
mcp_server = types.ModuleType('mcp.server')
sys.modules['mcp.server'] = mcp_server

# Now we can import the local module
spec = importlib.util.spec_from_file_location("mcp.fetch_report", os.path.abspath(os.path.dirname(__file__) + "/../mcp/fetch_report.py"))
local_mcp_fetch_report = importlib.util.module_from_spec(spec)
sys.modules['mcp.fetch_report'] = local_mcp_fetch_report

# Before executing, mock out the import of _handle_cached_sec_fetch
import unittest.mock
with unittest.mock.patch.dict('sys.modules', {'mcp.server': types.ModuleType('mcp.server')}):
    sys.modules['mcp.server']._handle_cached_sec_fetch = lambda *args, **kwargs: None
    spec.loader.exec_module(local_mcp_fetch_report)

run_fetch_report = local_mcp_fetch_report.run_fetch_report


def test_validation_errors():
    res = run_fetch_report("sess-1", report_type="invalid", tickers=["AAPL"])
    assert "Invalid report_type" in res["error"]

    res = run_fetch_report("sess-1", report_type="just_financials", tickers=[])
    assert "cannot be empty" in res["error"]

    res = run_fetch_report("sess-1", report_type="just_financials", tickers=["  ", ""])
    assert "valid ticker strings" in res["error"]


@patch("mcp.fetch_report._handle_cached_sec_fetch")
def test_just_financials_routing(mock_sec):
    mock_sec.return_value = {"file_id": "file-1", "scope_applied": {}}
    res = run_fetch_report(
        "sess-1",
        report_type="just_financials",
        tickers=["AAPL", " MSFT "],
        years=[2023],
    )
    assert res["success"] is True
    assert len(res["results"]) == 2
    assert res["results"][0]["ticker"] == "AAPL"
    assert res["results"][1]["ticker"] == "MSFT"

    # Verify underlying call args
    mock_sec.assert_any_call(
        "sess-1",
        company_name=None,
        ticker="AAPL",
        fiscal_years=[2023],
        max_years=1,
        include_annual=True,
        include_quarterly=False,
        statements=["income", "balance", "cashflow"],
    )


@patch("mcp.fetch_report.list_10k_fiscal_years")
@patch("mcp.fetch_report.resolve_or_ingest_sec")
def test_full_report_routing_with_years(mock_resolve, mock_list):
    mock_resolve.return_value = type(
        "R",
        (),
        {
            "success": True,
            "document_id": "doc-1",
            "filing_key": "AAPL_2024_10K",
            "from_cache": False,
        },
    )()
    res = run_fetch_report(
        "sess-1",
        report_type="full_report",
        tickers=["AAPL"],
        years=[2024],
    )
    assert res["success"] is True
    assert len(res["results"]) == 1
    assert res["results"][0]["year"] == 2024
    mock_list.assert_not_called()
    mock_resolve.assert_called_once_with(
        session_id="sess-1", ticker="AAPL", fiscal_year=2024
    )


@patch("mcp.fetch_report.list_10k_fiscal_years")
@patch("mcp.fetch_report.resolve_or_ingest_sec")
def test_full_report_routing_latest(mock_resolve, mock_list):
    mock_list.return_value = [2025]
    mock_resolve.return_value = type(
        "R",
        (),
        {
            "success": True,
            "document_id": "doc-1",
            "filing_key": "WMT_2025_10K",
            "from_cache": True,
        },
    )()
    res = run_fetch_report(
        "sess-1",
        report_type="full_report",
        tickers=["WMT"],
    )
    assert res["success"] is True
    assert res["results"][0]["year"] == 2025
    mock_list.assert_called_once_with("WMT", 1)
    mock_resolve.assert_called_once_with(
        session_id="sess-1", ticker="WMT", fiscal_year=2025
    )


@patch("mcp.fetch_report.list_10k_fiscal_years")
def test_full_report_no_filings(mock_list):
    mock_list.return_value = []
    res = run_fetch_report(
        "sess-1",
        report_type="full_report",
        tickers=["WMT"],
    )
    assert res["success"] is False
    assert "No 10-K filings found" in res["errors"][0]
