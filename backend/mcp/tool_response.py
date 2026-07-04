"""Uniform MCP tool response envelope."""

from __future__ import annotations

import os
from typing import Any

VIEW_BASE_URL = os.getenv("VIEW_BASE_URL", "http://localhost:5173").rstrip("/")

SYSTEM_NOTE = "CRITICAL: Pass this session_id into all future tool calls."


def view_url(session_id: str) -> str:
    return f"{VIEW_BASE_URL}/s/{session_id}"


def tool_response(sid: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": sid,
        "data": {**payload, "view_url": view_url(sid)},
        "system_note": SYSTEM_NOTE,
    }
