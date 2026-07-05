"""Explicit workspace session resolution for MCP tools (no header/ctx binding)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from store import _validate_session_id, create_session, session_exists

SESSION_ID_PARAM_DESC = (
    "REQUIRED on all tools except start_session. UUID from a prior tool response "
    "top-level session_id, or pasted from the dashboard (Session id box / /s/{uuid}). "
    "Do NOT omit — if no session exists yet, ask the user then call start_session first."
)

SESSION_REQUIRED_MESSAGE = (
    "No session_id provided. Ask the user: "
    '"Do you have an existing session id from your dashboard, or should I create a new workspace?" '
    "If they want new, call start_session first. If they paste a UUID, pass it here."
)


@dataclass(frozen=True)
class SessionResolveError:
    error: str
    message: str
    suggest_action: str
    provided_session_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "error": self.error,
            "message": self.message,
            "suggest_action": self.suggest_action,
        }
        if self.provided_session_id is not None:
            out["provided_session_id"] = self.provided_session_id
        return out


def _session_not_found_error(session_id: str) -> SessionResolveError:
    return SessionResolveError(
        error="session_not_found",
        message=(
            f"Session {session_id} not found (expired or invalid). "
            "Ask the user for a different id or call start_session to create a new workspace."
        ),
        suggest_action="ask_user_or_start_session",
        provided_session_id=session_id,
    )


def _invalid_session_id_error(raw: str) -> SessionResolveError:
    return SessionResolveError(
        error="session_invalid",
        message=(
            f"Invalid session_id format: {raw!r}. "
            "Ask the user for a valid UUID from their dashboard or create a new workspace via start_session."
        ),
        suggest_action="ask_user_or_start_session",
        provided_session_id=raw,
    )


def require_session(session_id: str | None) -> tuple[str | None, SessionResolveError | None]:
    """
    Require an existing workspace session. Used by all tools except start_session.

    - None/empty → session_required error
    - Invalid UUID → session_invalid error
    - Valid UUID + folder missing → session_not_found error
    - Valid UUID + folder exists → reuse
    """
    if not session_id or not session_id.strip():
        return None, SessionResolveError(
            error="session_required",
            message=SESSION_REQUIRED_MESSAGE,
            suggest_action="ask_user_or_start_session",
        )

    raw = session_id.strip()
    try:
        sid = _validate_session_id(raw)
    except ValueError:
        return None, _invalid_session_id_error(raw)

    if not session_exists(sid):
        return None, _session_not_found_error(sid)

    return sid, None


def start_session_resolve(
    session_id: str | None,
) -> tuple[str | None, bool, SessionResolveError | None]:
    """
    Resolve session for start_session only.

    - None/empty → create new session
    - Valid UUID + folder exists → attach (reused)
    - Valid UUID + folder missing → session_not_found error
    - Invalid UUID → session_invalid error
    """
    if not session_id or not session_id.strip():
        return create_session(), False, None

    raw = session_id.strip()
    try:
        sid = _validate_session_id(raw)
    except ValueError:
        return None, False, _invalid_session_id_error(raw)

    if session_exists(sid):
        return sid, True, None

    return None, False, _session_not_found_error(sid)
