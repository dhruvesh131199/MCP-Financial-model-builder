"""Tests for query_rag MCP tool."""

from __future__ import annotations

from unittest.mock import patch

import store as store_module
from mcp.query_rag import run_query_rag
from mcp.tool_response import SYSTEM_NOTE, tool_response
from store import create_session


def test_run_query_rag_invalid_mode():
    sid = "00000000-0000-4000-8000-000000000099"
    result = run_query_rag(mode="bogus", session_id=sid)  # type: ignore[arg-type]
    assert "error" in result
    assert "retrieve" in result["error"]


def test_run_query_rag_reset(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()
    result = run_query_rag(mode="reset", session_id=sid)
    assert result["mode"] == "reset"


def test_query_rag_tool_envelope(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    sid = create_session()
    mock_payload = {
        "mode": "retrieve",
        "loop": 1,
        "new_parent": {
            "parent_id": "NVDA_2025_10K_P_01",
            "ticker": "NVDA",
            "year": 2025,
            "filing_key": "NVDA_2025_10K",
            "label": "NVDA · 10-K · FY2025 · section #1",
            "content": "risk text",
        },
        "message": "Loop 1 done",
    }

    out = tool_response(sid, mock_payload)

    assert out["session_id"] == sid
    assert out["system_note"] == SYSTEM_NOTE
    assert out["data"]["new_parent"]["parent_id"] == "NVDA_2025_10K_P_01"
    assert out["data"]["view_url"].endswith(f"/s/{sid}")


def test_run_query_rag_retrieve_mocked(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()

    with patch(
        "mcp.query_rag.retrieve_loop",
        return_value={"mode": "retrieve", "loop": 1, "ticker": "NVDA"},
    ) as mock_retrieve:
        result = run_query_rag(
            mode="retrieve",
            session_id=sid,
            query="test",
            ticker="NVDA",
        )
    assert result["mode"] == "retrieve"
    mock_retrieve.assert_called_once_with(
        sid,
        "test",
        ticker="NVDA",
        original_question=None,
        top_k=10,
    )
