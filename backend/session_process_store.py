"""Transport-agnostic in-flight process files for session dashboards.

Writers (MCP, REST, …) upsert JSON under data/sessions/{id}/processes/.
The dashboard polls workspace.processes and shows a Processing sidebar.

delete_process marks expires_at (~3s) instead of using background threads —
list_processes removes expired files on poll (reload-safe, one place for all transports).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from store import _session_dir, session_exists

# Hold completed chips so the dashboard can paint Done / 100% before removal.
DEFAULT_DELETE_DELAY_SECONDS = 3.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def processes_dir(session_id: str) -> Path:
    return _session_dir(session_id) / "processes"


def _process_path(session_id: str, process_id: str) -> Path:
    safe = process_id.strip()
    if not safe or "/" in safe or "\\" in safe or ".." in safe:
        raise ValueError("Invalid process_id")
    return processes_dir(session_id) / f"{safe}.json"


def _parse_expires_at(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        exp = datetime.fromisoformat(raw.strip())
    except ValueError:
        return None
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp


def _unlink_quiet(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _touch_change_stamp(session_id: str) -> None:
    """Bump processes/.last_change so workspace.updated_at moves when chips clear."""
    root = processes_dir(session_id)
    try:
        root.mkdir(parents=True, exist_ok=True)
        (root / ".last_change").write_text(_utc_now_iso(), encoding="utf-8")
    except OSError:
        pass


def _is_expired(data: dict, *, now: datetime) -> bool:
    exp = _parse_expires_at(data.get("expires_at"))
    if exp is not None:
        return exp <= now
    # Orphan Done chips (e.g. old Timer path never set expires_at)
    if int(data.get("progress") or 0) >= 100:
        updated = _parse_expires_at(data.get("updated_at"))
        if updated is not None:
            return updated + timedelta(seconds=DEFAULT_DELETE_DELAY_SECONDS) <= now
        return True
    return False


def list_processes(session_id: str) -> list[dict]:
    """List active process chips; drop any whose expires_at has passed."""
    if not session_exists(session_id):
        return []
    root = processes_dir(session_id)
    if not root.is_dir():
        return []
    now = _utc_now()
    out: list[dict] = []
    removed = False
    for path in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict) or not data.get("id"):
            continue
        if _is_expired(data, now=now):
            _unlink_quiet(path)
            removed = True
            continue
        out.append(data)
    if removed:
        _touch_change_stamp(session_id)
    return out


def upsert_process(
    session_id: str,
    process_id: str | None = None,
    *,
    source: str,
    process_name: str,
    message: str,
    progress: int | float,
) -> dict:
    """Create or overwrite a process file. Returns the written payload."""
    if not session_exists(session_id):
        raise ValueError("Session not found")
    pid = (process_id or str(uuid.uuid4())).strip()
    clamped = max(0, min(100, int(round(float(progress)))))
    payload = {
        "id": pid,
        "source": source,
        "process_name": process_name,
        "message": message,
        "progress": clamped,
        "updated_at": _utc_now_iso(),
    }
    root = processes_dir(session_id)
    root.mkdir(parents=True, exist_ok=True)
    path = _process_path(session_id, pid)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def delete_process(
    session_id: str,
    process_id: str,
    *,
    delay_seconds: float = DEFAULT_DELETE_DELAY_SECONDS,
) -> None:
    """Remove a process file, or mark it to expire after delay_seconds.

    Default ~3s hold so Done/100% is visible. Cleanup happens on the next
    list_processes / workspace poll — no background threads (reload-safe).
    Pass delay_seconds=0 for immediate delete (tests / force-clear).
    """
    if not session_exists(session_id):
        return
    path = _process_path(session_id, process_id)
    if not path.exists():
        return
    if delay_seconds <= 0:
        _unlink_quiet(path)
        _touch_change_stamp(session_id)
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _unlink_quiet(path)
        return
    if not isinstance(data, dict):
        _unlink_quiet(path)
        return
    data["expires_at"] = (_utc_now() + timedelta(seconds=delay_seconds)).isoformat()
    data["updated_at"] = _utc_now_iso()
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        _unlink_quiet(path)


def processes_mtime(session_id: str) -> str | None:
    """Latest mtime among process files / change stamp (for workspace.updated_at)."""
    if not session_exists(session_id):
        return None
    # Expire stale chips first so mtime matches what the UI will see.
    list_processes(session_id)
    root = processes_dir(session_id)
    if not root.is_dir():
        return None
    latest: float | None = None
    for path in list(root.glob("*.json")) + [root / ".last_change"]:
        if not path.exists():
            continue
        try:
            m = path.stat().st_mtime
        except OSError:
            continue
        if latest is None or m > latest:
            latest = m
    if latest is None:
        return None
    return datetime.fromtimestamp(latest, tz=timezone.utc).isoformat()
