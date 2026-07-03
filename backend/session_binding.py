"""Map MCP client connections to app workspace session folders."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mcp.server.fastmcp import Context

from store import create_session, session_exists

DATA_DIR = Path(__file__).resolve().parent / "data"
BINDINGS_PATH = DATA_DIR / "mcp_bindings.json"

_bindings: dict[str, str] = {}


def _load_bindings() -> None:
    global _bindings
    if BINDINGS_PATH.exists():
        _bindings = json.loads(BINDINGS_PATH.read_text(encoding="utf-8"))


def _save_bindings() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BINDINGS_PATH.write_text(json.dumps(_bindings, indent=2), encoding="utf-8")


_load_bindings()


def mcp_connection_key(ctx: Context) -> str:
    """Stable key for this Cursor/Claude MCP connection."""
    request = ctx.request_context.request
    if request is not None and hasattr(request, "headers"):
        headers = request.headers
        # Prefer explicit per-chat IDs forwarded by MCP clients.
        for name in (
            "mcp-session-id",
            "x-mcp-session-id",
            "mcp-session",
            "x-session-id",
            "x-conversation-id",
            "anthropic-conversation-id",
            "x-claude-conversation-id",
            "openai-conversation-id",
        ):
            value = headers.get(name)
            if value:
                return f"mcp:{value}"
        # Some clients forward identifiers in query params instead of headers.
        query = getattr(request, "query_params", None)
        if query is not None:
            for name in ("mcp_session_id", "session_id", "conversation_id"):
                value = query.get(name)
                if value:
                    return f"mcp:{value}"
        # Fallback for clients that do not send a conversation/session id.
        # Hash sensitive values so they are not persisted in plaintext.
        auth = headers.get("authorization") or headers.get("x-api-key") or ""
        user_agent = headers.get("user-agent") or ""
        host = headers.get("host") or ""
        if auth or user_agent or host:
            digest = hashlib.sha256(
                f"{auth}|{user_agent}|{host}".encode("utf-8")
            ).hexdigest()[:24]
            return f"fp:{digest}"
    return f"conn:{id(ctx.session)}"


def bind_connection(mcp_key: str, app_session_id: str) -> None:
    _bindings[mcp_key] = app_session_id
    _save_bindings()


def resolve_workspace_session(
    ctx: Context,
    explicit_session_id: str | None = None,
) -> str:
    """
    Return the workspace session for this MCP connection.
    Creates one automatically if none exists yet.
    """
    mcp_key = mcp_connection_key(ctx)

    if explicit_session_id:
        from store import _validate_session_id

        sid = _validate_session_id(explicit_session_id)
        if not session_exists(sid):
            raise ValueError(f"Session not found: {sid}")
        bind_connection(mcp_key, sid)
        return sid

    if mcp_key in _bindings and session_exists(_bindings[mcp_key]):
        return _bindings[mcp_key]

    sid = create_session()
    bind_connection(mcp_key, sid)
    return sid
