"""Tests for REST financials fetch process lifecycle."""

from __future__ import annotations

from unittest.mock import patch

from services.financials_fetch_service import run_session_financials_fetch


@patch("services.financials_fetch_service.delete_process")
@patch("services.financials_fetch_service.upsert_process")
@patch("services.financials_fetch_service.handle_cached_sec_fetch")
def test_rest_fetch_process_lifecycle(mock_sec, mock_upsert, mock_delete):
    mock_sec.return_value = {"file_id": "file-1", "scope_applied": {}}
    calls: list[dict] = []

    def _upsert(session_id, process_id=None, **kwargs):
        pid = process_id or "proc-rest"
        entry = {"id": pid, **kwargs}
        calls.append(entry)
        return entry

    mock_upsert.side_effect = _upsert

    res = run_session_financials_fetch(
        "sess-1",
        tickers=["AAPL", "MSFT"],
        years=[2023],
    )
    assert res["success"] is True
    assert len(res["results"]) == 2

    assert calls[0]["source"] == "rest"
    assert calls[0]["process_name"] == "Fetching SEC files"
    assert calls[0]["message"] == "Starting…"
    assert calls[0]["progress"] == 2
    assert "AAPL" in calls[1]["message"]
    assert calls[1]["progress"] == 2
    assert "MSFT" in calls[2]["message"]
    assert calls[2]["progress"] == 51
    assert calls[3]["message"] == "Done…"
    assert calls[3]["progress"] == 100
    assert mock_upsert.call_count == 4
    mock_delete.assert_called_once_with("sess-1", "proc-rest")


@patch("services.financials_fetch_service.delete_process")
@patch("services.financials_fetch_service.upsert_process")
@patch("services.financials_fetch_service.handle_cached_sec_fetch")
def test_rest_fetch_deletes_process_on_error(mock_sec, mock_upsert, mock_delete):
    mock_upsert.return_value = {"id": "proc-err"}
    mock_sec.side_effect = RuntimeError("SEC down")

    try:
        run_session_financials_fetch("sess-1", tickers=["AAPL"])
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "SEC down" in str(exc)
    mock_delete.assert_called_once_with("sess-1", "proc-err")
