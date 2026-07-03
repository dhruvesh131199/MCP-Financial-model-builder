from __future__ import annotations

import sys
import types

sys.modules.setdefault("mcp", types.ModuleType("mcp"))
sys.modules.setdefault("mcp.server", types.ModuleType("mcp.server"))
fastmcp_mod = types.ModuleType("mcp.server.fastmcp")
fastmcp_mod.Context = object
sys.modules.setdefault("mcp.server.fastmcp", fastmcp_mod)

import session_binding as sb


def _ctx(
    *,
    headers: dict[str, str] | None = None,
    query_params: dict[str, str] | None = None,
) -> types.SimpleNamespace:
    request = types.SimpleNamespace(
        headers=headers or {},
        query_params=query_params or {},
    )
    request_context = types.SimpleNamespace(request=request)
    return types.SimpleNamespace(
        request_context=request_context,
        session=object(),
    )


def test_mcp_connection_key_prefers_header_session_id():
    key = sb.mcp_connection_key(_ctx(headers={"mcp-session-id": "abc123"}))
    assert key == "mcp:abc123"


def test_mcp_connection_key_accepts_claude_conversation_header():
    key = sb.mcp_connection_key(
        _ctx(headers={"anthropic-conversation-id": "conv-42"})
    )
    assert key == "mcp:conv-42"


def test_mcp_connection_key_uses_stable_fingerprint_fallback():
    ctx1 = _ctx(
        headers={
            "authorization": "Bearer secret-token",
            "user-agent": "claude-client",
            "host": "example.com",
        }
    )
    ctx2 = _ctx(
        headers={
            "authorization": "Bearer secret-token",
            "user-agent": "claude-client",
            "host": "example.com",
        }
    )
    key1 = sb.mcp_connection_key(ctx1)
    key2 = sb.mcp_connection_key(ctx2)
    assert key1.startswith("fp:")
    assert key1 == key2


def test_resolve_workspace_session_reuses_binding(monkeypatch):
    monkeypatch.setattr(sb, "_bindings", {}, raising=False)
    monkeypatch.setattr(sb, "_save_bindings", lambda: None)
    monkeypatch.setattr(sb, "session_exists", lambda sid: sid == "sess-1")
    monkeypatch.setattr(sb, "create_session", lambda: "sess-1")

    ctx = _ctx(headers={"mcp-session-id": "sticky"})
    sid1 = sb.resolve_workspace_session(ctx)
    sid2 = sb.resolve_workspace_session(ctx)

    assert sid1 == "sess-1"
    assert sid2 == "sess-1"

