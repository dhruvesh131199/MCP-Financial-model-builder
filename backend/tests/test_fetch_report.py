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


@patch("mcp.fetch_report.delete_process")
@patch("mcp.fetch_report.upsert_process")
@patch("mcp.fetch_report.handle_cached_sec_fetch")
def test_just_financials_routing(mock_sec, mock_upsert, mock_delete):
    mock_sec.return_value = {"file_id": "file-1", "scope_applied": {}}
    mock_upsert.side_effect = lambda *a, **k: {
        "id": k.get("process_id") or (a[1] if len(a) > 1 and a[1] else "proc-1"),
        "source": "mcp",
        "process_name": k.get("process_name", "Fetching SEC files"),
        "message": k.get("message", ""),
        "progress": int(k.get("progress", 0)),
    }

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
    # start + one update per ticker + Done at 100
    assert mock_upsert.call_count == 4
    mock_delete.assert_called_once_with("sess-1", "proc-1")


@patch("mcp.fetch_report.delete_process")
@patch("mcp.fetch_report.upsert_process")
@patch("mcp.fetch_report.handle_cached_sec_fetch")
def test_just_financials_process_lifecycle(mock_sec, mock_upsert, mock_delete):
    mock_sec.return_value = {"file_id": "file-1", "scope_applied": {}}
    calls: list[dict] = []

    def _upsert(session_id, process_id=None, **kwargs):
        pid = process_id or "proc-lifecycle"
        entry = {"id": pid, **kwargs}
        calls.append(entry)
        return entry

    mock_upsert.side_effect = _upsert

    res = run_fetch_report(
        "sess-1",
        report_type="just_financials",
        tickers=["AAPL", "MSFT"],
    )
    assert res["success"] is True
    assert calls[0]["message"] == "Starting…"
    assert calls[0]["progress"] == 2
    assert "AAPL" in calls[1]["message"]
    assert calls[1]["progress"] == 2
    assert "MSFT" in calls[2]["message"]
    assert calls[2]["progress"] == 51
    assert calls[3]["message"] == "Done…"
    assert calls[3]["progress"] == 100
    mock_delete.assert_called_once_with("sess-1", "proc-lifecycle")


@patch("mcp.fetch_report.delete_process")
@patch("mcp.fetch_report.upsert_process")
@patch("mcp.fetch_report.handle_cached_sec_fetch")
def test_just_financials_deletes_process_on_error(mock_sec, mock_upsert, mock_delete):
    mock_upsert.return_value = {"id": "proc-err"}
    mock_sec.side_effect = RuntimeError("SEC down")

    try:
        run_fetch_report(
            "sess-1",
            report_type="just_financials",
            tickers=["AAPL"],
        )
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "SEC down" in str(exc)
    mock_delete.assert_called_once_with("sess-1", "proc-err")



@patch("mcp.fetch_report.list_10k_fiscal_years")
@patch("mcp.fetch_report.resolve_or_ingest_sec_async")
def test_full_report_routing_with_years(mock_resolve, mock_list):
    async def _fake_resolve(**kwargs):
        return type(
            "R",
            (),
            {
                "success": True,
                "document_id": "doc-1",
                "filing_key": "AAPL_2024_10K",
                "from_cache": False,
                "ticker": "AAPL",
                "year": 2024,
                "error": None,
            },
        )()

    mock_resolve.side_effect = _fake_resolve
    res = run_fetch_report(
        "sess-1",
        report_type="full_report",
        tickers=["AAPL"],
        years=[2024],
    )
    assert res["success"] is True
    assert len(res["results"]) == 1
    assert res["results"][0]["year"] == 2024
    assert "duration_seconds" in res
    mock_list.assert_not_called()
    mock_resolve.assert_called_once_with(
        session_id="sess-1", ticker="AAPL", fiscal_year=2024
    )


@patch("mcp.fetch_report.list_10k_fiscal_years")
@patch("mcp.fetch_report.resolve_or_ingest_sec_async")
def test_full_report_routing_latest(mock_resolve, mock_list):
    mock_list.return_value = [2025]

    async def _fake_resolve(**kwargs):
        return type(
            "R",
            (),
            {
                "success": True,
                "document_id": "doc-1",
                "filing_key": "WMT_2025_10K",
                "from_cache": True,
                "ticker": "WMT",
                "year": 2025,
                "error": None,
            },
        )()

    mock_resolve.side_effect = _fake_resolve
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


@patch("mcp.fetch_report.resolve_or_ingest_sec_async")
def test_full_report_gather_multiple_pairs(mock_resolve):
    async def _fake_resolve(**kwargs):
        return type(
            "R",
            (),
            {
                "success": True,
                "document_id": f"doc-{kwargs['ticker']}-{kwargs['fiscal_year']}",
                "filing_key": f"{kwargs['ticker']}_{kwargs['fiscal_year']}_10K",
                "from_cache": False,
                "ticker": kwargs["ticker"],
                "year": kwargs["fiscal_year"],
                "error": None,
            },
        )()

    mock_resolve.side_effect = _fake_resolve

    res = run_fetch_report(
        "sess-1",
        report_type="full_report",
        tickers=["AAPL", "MSFT"],
        years=[2024, 2023],
    )

    assert res["success"] is True
    assert len(res["results"]) == 4
    assert mock_resolve.call_count == 4


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
