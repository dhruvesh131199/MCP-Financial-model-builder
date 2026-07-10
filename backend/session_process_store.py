"""Transport-agnostic in-flight process files for session dashboards.

Writers (MCP, REST, …) upsert JSON under data/sessions/{id}/processes/.
The dashboard polls workspace.processes and shows a Processing sidebar.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from store import _session_dir, session_exists


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def processes_dir(session_id: str) -> Path:
    return _session_dir(session_id) / "processes"


def _process_path(session_id: str, process_id: str) -> Path:
    safe = process_id.strip()
    if not safe or "/" in safe or "\\" in safe or ".." in safe:
        raise ValueError("Invalid process_id")
    return processes_dir(session_id) / f"{safe}.json"


def list_processes(session_id: str) -> list[dict]:
    if not session_exists(session_id):
        return []
    root = processes_dir(session_id)
    if not root.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and data.get("id"):
            out.append(data)
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
        "updated_at": _utc_now(),
    }
    root = processes_dir(session_id)
    root.mkdir(parents=True, exist_ok=True)
    path = _process_path(session_id, pid)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def delete_process(session_id: str, process_id: str) -> None:
    if not session_exists(session_id):
        return
    path = _process_path(session_id, process_id)
    if path.exists():
        path.unlink()


def processes_mtime(session_id: str) -> str | None:
    """Latest mtime among process files (for workspace.updated_at)."""
    if not session_exists(session_id):
        return None
    root = processes_dir(session_id)
    if not root.is_dir():
        return None
    latest: float | None = None
    for path in root.glob("*.json"):
        try:
            m = path.stat().st_mtime
        except OSError:
            continue
        if latest is None or m > latest:
            latest = m
    if latest is None:
        return None
    return datetime.fromtimestamp(latest, tz=timezone.utc).isoformat()
