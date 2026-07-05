"""Tests for MCP tool response envelope (session_id echo)."""

from __future__ import annotations

import store as store_module
from mcp.tool_response import SYSTEM_NOTE, tool_response, view_url
from session_resolve import require_session, start_session_resolve
from store import create_session


def test_tool_response_shape():
    sid = "00000000-0000-4000-8000-000000000099"
    out = tool_response(sid, {"message": "ok", "success": True})
    assert out["session_id"] == sid
    assert out["system_note"] == SYSTEM_NOTE
    assert out["data"]["message"] == "ok"
    assert out["data"]["success"] is True
    assert out["data"]["view_url"] == view_url(sid)


def test_tool_response_session_error_has_null_session_id():
    out = tool_response(
        None,
        {
            "error": "session_required",
            "message": "Ask the user",
            "suggest_action": "ask_user_or_start_session",
        },
    )
    assert out["session_id"] is None
    assert out["data"]["error"] == "session_required"
    assert out["data"]["view_url"] is None


def test_start_session_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    sid, reused, err = start_session_resolve(None)
    assert err is None
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


def test_require_session_reuses_for_tool_chain(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    sid = create_session()
    sid2, err = require_session(sid)
    assert err is None
    assert sid2 == sid

    out = tool_response(sid2, {"error": "bad ticker"})
    assert out["session_id"] == sid2
    assert out["data"]["error"] == "bad ticker"


def test_require_session_none_for_tool_chain(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    sid, err = require_session(None)
    assert sid is None
    assert err is not None
    out = tool_response(None, err.to_dict())
    assert out["session_id"] is None
    assert out["data"]["error"] == "session_required"
