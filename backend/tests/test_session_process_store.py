"""Tests for session_process_store (in-flight process JSON files)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from store import create_session, load_workspace
from session_process_store import (
    delete_process,
    list_processes,
    processes_mtime,
    upsert_process,
)


def test_upsert_list_delete_and_workspace():
    sid = create_session()
    assert list_processes(sid) == []
    assert processes_mtime(sid) is None

    created = upsert_process(
        sid,
        source="mcp",
        process_name="Fetching SEC files",
        message="Starting…",
        progress=2,
    )
    assert created["id"]
    assert created["progress"] == 2
    assert created["process_name"] == "Fetching SEC files"

    listed = list_processes(sid)
    assert len(listed) == 1
    assert listed[0]["message"] == "Starting…"
    assert processes_mtime(sid) is not None

    upsert_process(
        sid,
        created["id"],
        source="mcp",
        process_name="Fetching SEC files",
        message="Fetching AAPL data…",
        progress=50,
    )
    listed = list_processes(sid)
    assert len(listed) == 1
    assert listed[0]["message"] == "Fetching AAPL data…"
    assert listed[0]["progress"] == 50

    ws = load_workspace(sid)
    assert ws is not None
    assert len(ws["processes"]) == 1
    assert ws["processes"][0]["id"] == created["id"]
    assert ws["updated_at"] is not None

    delete_process(sid, created["id"], delay_seconds=0)
    assert list_processes(sid) == []
    ws2 = load_workspace(sid)
    assert ws2 is not None
    assert ws2["processes"] == []


def test_delete_process_marks_expires_at_then_list_clears():
    sid = create_session()
    created = upsert_process(
        sid,
        source="rest",
        process_name="Fetching SEC files",
        message="Done…",
        progress=100,
    )
    delete_process(sid, created["id"], delay_seconds=3.0)
    listed = list_processes(sid)
    assert len(listed) == 1
    assert listed[0]["progress"] == 100
    assert listed[0]["message"] == "Done…"
    assert "expires_at" in listed[0]

    # Force expiry in the past — next list should unlink.
    from session_process_store import _process_path
    import json

    path = _process_path(sid, created["id"])
    data = json.loads(path.read_text(encoding="utf-8"))
    data["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    path.write_text(json.dumps(data), encoding="utf-8")

    assert list_processes(sid) == []
    assert not path.exists()


def test_orphan_done_without_expires_at_clears_after_delay():
    """Stuck Done chips from the old Timer path still get cleaned on poll."""
    import json
    from session_process_store import _process_path

    sid = create_session()
    created = upsert_process(
        sid,
        source="rest",
        process_name="Fetching SEC files",
        message="Done…",
        progress=100,
    )
    path = _process_path(sid, created["id"])
    data = json.loads(path.read_text(encoding="utf-8"))
    data["updated_at"] = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    data.pop("expires_at", None)
    path.write_text(json.dumps(data), encoding="utf-8")

    assert list_processes(sid) == []
    assert not path.exists()


def test_progress_clamped_to_0_100():
    sid = create_session()
    over = upsert_process(
        sid,
        source="rest",
        process_name="Test",
        message="hi",
        progress=150,
    )
    assert over["progress"] == 100
    under = upsert_process(
        sid,
        over["id"],
        source="rest",
        process_name="Test",
        message="hi",
        progress=-5,
    )
    assert under["progress"] == 0
