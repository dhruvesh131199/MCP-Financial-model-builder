"""Tests for explicit session_id resolution (no MCP header binding)."""

from __future__ import annotations

import store as store_module
from session_resolve import resolve_or_create_session
from store import create_session, session_exists


def test_resolve_or_create_session_none_creates_new(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    sid, reused = resolve_or_create_session(None)
    assert reused is False
    assert session_exists(sid)


def test_resolve_or_create_session_reuses_existing(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    existing = create_session()
    sid, reused = resolve_or_create_session(existing)
    assert sid == existing
    assert reused is True


def test_resolve_or_create_session_missing_folder_creates_new(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    stale_id = "00000000-0000-4000-8000-000000000001"
    sid, reused = resolve_or_create_session(stale_id)
    assert reused is False
    assert sid != stale_id
    assert session_exists(sid)


def test_resolve_or_create_session_invalid_uuid_creates_new(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    sid, reused = resolve_or_create_session("not-a-uuid")
    assert reused is False
    assert session_exists(sid)
