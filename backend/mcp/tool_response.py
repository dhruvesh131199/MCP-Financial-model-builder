"""Uniform MCP tool response envelope."""

from __future__ import annotations

import os
from typing import Any

VIEW_BASE_URL = os.getenv("VIEW_BASE_URL", "http://localhost:5173").rstrip("/")

SYSTEM_NOTE = (
    "CRITICAL: Pass session_id from every tool response into all future tool calls. "
    "If you have no session_id yet, ask the user before calling workspace tools. "
    "Only start_session creates a new workspace."
)


def view_url(session_id: str) -> str:
    return f"{VIEW_BASE_URL}/s/{session_id}"


def tool_response(sid: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    if sid:
        data["view_url"] = view_url(sid)
    else:
        data.setdefault("view_url", None)

    return {
        "session_id": sid,
        "data": data,
        "system_note": SYSTEM_NOTE,
    }
