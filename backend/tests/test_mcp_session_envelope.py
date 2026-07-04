"""Tests for MCP tool response envelope (session_id echo)."""

from __future__ import annotations

import store as store_module
from mcp.tool_response import SYSTEM_NOTE, tool_response, view_url
from session_resolve import resolve_or_create_session
from store import create_session


def test_tool_response_shape():
    sid = "00000000-0000-4000-8000-000000000099"
    out = tool_response(sid, {"message": "ok", "success": True})
    assert out["session_id"] == sid
    assert out["system_note"] == SYSTEM_NOTE
    assert out["data"]["message"] == "ok"
    assert out["data"]["success"] is True
    assert out["data"]["view_url"] == view_url(sid)


def test_start_session_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    sid, reused = resolve_or_create_session(None)
    assert reused is False

    out = tool_response(
        sid,
        {
            "created_new": True,
            "reused_existing": False,
            "message": "Workspace ready.",
        },
    )
    assert out["session_id"] == sid
    assert out["data"]["created_new"] is True


def test_resolve_or_create_reuses_for_tool_chain(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    sid = create_session()
    sid2, reused = resolve_or_create_session(sid)
    assert sid2 == sid
    assert reused is True

    out = tool_response(sid2, {"error": "bad ticker"})
    assert out["session_id"] == sid2
    assert out["data"]["error"] == "bad ticker"
