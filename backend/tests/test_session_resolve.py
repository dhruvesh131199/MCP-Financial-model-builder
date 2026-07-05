"""Tests for explicit session_id resolution (no MCP header binding)."""

from __future__ import annotations

import store as store_module
from session_resolve import require_session, start_session_resolve
from store import create_session, session_exists


def test_require_session_none_returns_error(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    sid, err = require_session(None)
    assert sid is None
    assert err is not None
    assert err.error == "session_required"


def test_require_session_reuses_existing(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    existing = create_session()
    sid, err = require_session(existing)
    assert err is None
    assert sid == existing


def test_require_session_missing_folder_returns_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    stale_id = "00000000-0000-4000-8000-000000000001"
    sid, err = require_session(stale_id)
    assert sid is None
    assert err is not None
    assert err.error == "session_not_found"
    assert err.provided_session_id == stale_id


def test_require_session_invalid_uuid_returns_error(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    sid, err = require_session("not-a-uuid")
    assert sid is None
    assert err is not None
    assert err.error == "session_invalid"


def test_start_session_resolve_none_creates_new(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    sid, reused, err = start_session_resolve(None)
    assert err is None
    assert reused is False
    assert sid is not None
    assert session_exists(sid)


def test_start_session_resolve_reuses_existing(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    existing = create_session()
    sid, reused, err = start_session_resolve(existing)
    assert err is None
    assert sid == existing
    assert reused is True


def test_start_session_resolve_missing_folder_returns_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    stale_id = "00000000-0000-4000-8000-000000000001"
    sid, reused, err = start_session_resolve(stale_id)
    assert sid is None
    assert reused is False
    assert err is not None
    assert err.error == "session_not_found"
