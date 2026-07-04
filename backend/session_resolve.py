"""Explicit workspace session resolution for MCP tools (no header/ctx binding)."""

from __future__ import annotations

from store import _validate_session_id, create_session, session_exists

SESSION_ID_PARAM_DESC = (
    "The UUID of the active workspace. STRICTLY REQUIRED if you are in an ongoing session. "
    "Look at your previous tool responses to find it. ONLY leave this blank if the user "
    "explicitly asks for a new session or you genuinely have no prior session ID."
)


def resolve_or_create_session(session_id: str | None) -> tuple[str, bool]:
    """
    Return (workspace_uuid, reused_existing).

    - None/empty → new session
    - Valid UUID + folder exists → reuse
    - Valid UUID + folder missing (TTL/deleted) → new session
    - Invalid UUID format → new session (lenient)
    """
    if session_id and session_id.strip():
        try:
            sid = _validate_session_id(session_id.strip())
            if session_exists(sid):
                return sid, True
        except ValueError:
            pass
    return create_session(), False
