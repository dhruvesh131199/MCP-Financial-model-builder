"""MCP server over HTTP. Anonymous sessions — auto-created per chat connection."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv
from mcp.server.fastmcp import Context, FastMCP

from engine.dcf import compute_dcf
from session_binding import resolve_workspace_session
from store import (
    REQUIRED_DCF_FIELDS,
    build_dcf_inputs_from_bundle,
    company_name_from_bundle,
    merge_model_inputs,
    save_dcf_model,
    summarize_input_bundle,
)

load_dotenv(BACKEND_ROOT / ".env")

VIEW_BASE_URL = os.getenv("VIEW_BASE_URL", "http://localhost:5173").rstrip("/")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))

INSTRUCTIONS = """
You help users build DCF (Discounted Cash Flow) valuation models.

MANDATORY WORKFLOW — follow in order:
1. start_session() — ALWAYS call this first when the user wants to build a model.
   Immediately share the view_url with the user.
2. Ask for missing assumptions one at a time or in a short list.
3. set_model_inputs(values={{...}}) — ONLY include fields the user explicitly stated
   in this conversation. Never guess or use industry defaults.
4. If set_model_inputs returns ready=false, ask for missing_required fields.
5. run_dcf() — ONLY when ready=true. Never pass inputs directly to run_dcf.

CRITICAL RULES:
- NEVER invent numbers (no default WACC, tax rate, growth, margins, etc.).
- NEVER build a DCF in prose or do arithmetic yourself — use tools only.
- NEVER call run_dcf until set_model_inputs reports ready=true.
- After EVERY tool call, show the user their view_url dashboard link.
- If the user only asks a question about an existing model, answer from tool results;
  do not recompute unless they ask to change assumptions.

Required fields: """ + ", ".join(REQUIRED_DCF_FIELDS) + """
Optional: net_debt, shares_outstanding, company_name
"""

mcp = FastMCP(
    "financial-models",
    instructions=INSTRUCTIONS,
    host=MCP_HOST,
    port=MCP_PORT,
)


def _view_url(session_id: str) -> str:
    return f"{VIEW_BASE_URL}/s/{session_id}"


def _with_session(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "view_url": _view_url(session_id),
        **payload,
    }


@mcp.tool()
def start_session(ctx: Context) -> dict:
    """
    REQUIRED first step for any new DCF build. Creates or reuses this chat's workspace.
    Always call this before collecting inputs. Returns view_url — share it with the user
    immediately so they can open their private dashboard.
    """
    session_id = resolve_workspace_session(ctx)
    url = _view_url(session_id)
    return {
        "session_id": session_id,
        "view_url": url,
        "message": (
            f"Workspace ready. Open your dashboard: {url} "
            "Next: ask the user for DCF assumptions, then call set_model_inputs "
            "with ONLY values they stated."
        ),
    }


@mcp.tool()
def set_model_inputs(
    values: dict[str, Any],
    ctx: Context,
    session_id: str | None = None,
) -> dict:
    """
    Record user-stated DCF assumptions on the server. Call after the user provides numbers.

    RULES:
    - Pass ONLY keys the user explicitly gave you in chat. Do not fill missing fields.
    - Allowed keys: base_revenue, revenue_growth, ebitda_margin, tax_rate, capex_pct,
      nwc_pct, wacc, terminal_growth, projection_years, net_debt, shares_outstanding,
      company_name
    - Returns missing_required and ready. If ready=false, ask the user for missing fields.
    - Do NOT call run_dcf until ready=true.
    """
    try:
        sid = resolve_workspace_session(ctx, session_id)
    except ValueError as exc:
        return {"error": str(exc)}

    if not values:
        return _with_session(
            sid,
            {
                "error": "values object is required",
                "example": {"wacc": 0.10, "terminal_growth": 0.02},
            },
        )

    try:
        summary = merge_model_inputs(sid, values)
    except KeyError:
        return {"error": "Session not found. Call start_session first."}

    msg = (
        "All required inputs recorded. Call run_dcf() now."
        if summary["ready"]
        else f"Still need from user: {', '.join(summary['missing_required'])}"
    )
    return _with_session(sid, {**summary, "message": msg})


@mcp.tool()
def run_dcf(ctx: Context, session_id: str | None = None) -> dict:
    """
    Build the DCF from inputs already stored via set_model_inputs. Does NOT accept
    inline numbers — the server enforces that inputs were recorded first.

    If not ready, returns missing_required instead of computing.
    Python computes all math; never calculate EV or FCF yourself.
  """
    try:
        sid = resolve_workspace_session(ctx, session_id)
    except ValueError as exc:
        return {"error": str(exc)}

    summary = summarize_input_bundle(sid)
    if not summary["ready"]:
        return _with_session(
            sid,
            {
                "success": False,
                "missing_required": summary["missing_required"],
                "filled": summary["filled"],
                "message": (
                    "Cannot run DCF yet. Ask the user for missing_required fields, "
                    "then call set_model_inputs before run_dcf."
                ),
            },
        )

    try:
        inputs = build_dcf_inputs_from_bundle(sid)
    except ValueError as exc:
        return _with_session(sid, {"success": False, "error": str(exc)})

    company_name = company_name_from_bundle(sid)
    result = compute_dcf(inputs, company_name=company_name)
    entry = save_dcf_model(sid, result.model_dump())
    url = _view_url(sid)

    return {
        "success": True,
        "session_id": sid,
        "view_url": url,
        "model_id": entry["id"],
        "model_name": entry["name"],
        "enterprise_value_millions": result.enterprise_value,
        "equity_value_millions": result.equity_value,
        "price_per_share": result.price_per_share,
        "message": f"DCF '{entry['name']}' saved. Open {url} to view and download.",
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
