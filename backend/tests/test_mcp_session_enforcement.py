"""Tests for session enforcement on MCP tools."""

from __future__ import annotations

import store as store_module
from mcp.tool_response import tool_response
from session_resolve import require_session, start_session_resolve
from store import create_session


def test_require_session_none_returns_session_required_envelope(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    sid, err = require_session(None)
    assert sid is None
    assert err is not None
    out = tool_response(None, err.to_dict())
    assert out["session_id"] is None
    assert out["data"]["error"] == "session_required"
    assert out["data"]["view_url"] is None


def test_require_session_valid_returns_sid(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    sid = create_session()
    resolved, err = require_session(sid)
    assert err is None
    assert resolved == sid


def test_start_session_creates_without_id(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    sid, reused, err = start_session_resolve(None)
    assert err is None
    assert reused is False
    assert sid is not None


def test_stale_session_id_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    stale = "00000000-0000-4000-8000-000000000099"
    sid, err = require_session(stale)
    assert sid is None
    assert err is not None
    assert err.error == "session_not_found"
