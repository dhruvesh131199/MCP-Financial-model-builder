"""Tests for RagIngestProgress and RAG ingest process lifecycle."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from helper.rag.resolve import RagResolveResult
from session_process_store import (
    RAG_INGEST_PROCESS_NAME,
    RagIngestProgress,
    list_processes,
)
from store import create_session


def test_rag_ingest_progress_start_report_finish():
    sid = create_session()
    prog = RagIngestProgress.start(sid, source="mcp", n_filings=1)
    assert prog.step == 98.0 / 5
    assert prog.progress == 2.0
    listed = list_processes(sid)
    assert len(listed) == 1
    assert listed[0]["process_name"] == RAG_INGEST_PROCESS_NAME
    assert listed[0]["message"].startswith("Starting")

    prog.report("AAPL 2023: already in database", advance_steps=5)
    assert prog.progress == 100.0
    listed = list_processes(sid)
    assert listed[0]["progress"] == 100
    assert "already in database" in listed[0]["message"]

    prog.finish()
    listed = list_processes(sid)
    assert len(listed) == 1
    assert listed[0].get("expires_at")


def test_rag_ingest_progress_five_steps_for_one_filing():
    sid = create_session()
    prog = RagIngestProgress.start(sid, source="rest", n_filings=1)
    for i in range(5):
        prog.report(f"step {i}", advance_steps=1)
    assert abs(prog.progress - 100.0) < 0.01
    prog.finish()


@patch("api.session_rag.resolve_or_ingest_sec")
def test_rest_rag_fetch_passes_progress(mock_resolve):
    from fastapi.testclient import TestClient

    from api.main import app

    mock_resolve.return_value = RagResolveResult(
        success=True,
        from_cache=True,
        status="ready",
        document_id="doc-1",
        filing_key="AAPL_2023_10K",
        rag_entry_id="rag-1",
        label="AAPL 2023 10-K",
        ticker="AAPL",
        year=2023,
        doctype="10K",
        source="sec_annual",
        parent_count=1,
        subchunk_count=2,
    )

    sid = create_session()
    client = TestClient(app)
    res = client.post(
        f"/api/sessions/{sid}/rag/ingest/fetch",
        json={"ticker": "AAPL", "fiscal_year": 2023},
    )
    assert res.status_code == 200
    mock_resolve.assert_called_once()
    assert mock_resolve.call_args.kwargs.get("progress") is not None
    assert isinstance(mock_resolve.call_args.kwargs["progress"], RagIngestProgress)


@patch("mcp.fetch_report.resolve_or_ingest_sec_async")
def test_mcp_full_report_passes_progress(mock_resolve):
    from mcp.fetch_report import run_fetch_report_async

    async def _resolved(**kwargs):
        assert kwargs.get("progress") is not None
        kwargs["progress"].report("AAPL 2023: already in database", advance_steps=5)
        return RagResolveResult(
            success=True,
            from_cache=True,
            status="ready",
            document_id="doc-1",
            filing_key="AAPL_2023_10K",
            rag_entry_id="rag-1",
            label="AAPL 2023 10-K",
            ticker="AAPL",
            year=2023,
            doctype="10K",
            source="sec_annual",
            parent_count=1,
            subchunk_count=2,
        )

    mock_resolve.side_effect = _resolved
    sid = create_session()

    with patch(
        "mcp.fetch_report._map_full_report_work_items",
        return_value=([("AAPL", 2023)], [], []),
    ):
        out = asyncio.run(
            run_fetch_report_async(
                sid,
                report_type="full_report",
                tickers=["AAPL"],
                years=[2023],
            )
        )
    assert out["success"] is True
    mock_resolve.assert_called_once()
    assert mock_resolve.call_args.kwargs.get("progress") is not None
