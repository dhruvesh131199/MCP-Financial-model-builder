"""MCP server over HTTP. Anonymous sessions — auto-created per chat connection."""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv
from mcp.server.fastmcp import Context, FastMCP

from engine.dcf import DcfInputs, compute_dcf
from session_binding import resolve_workspace_session
from store import save_dcf_model

load_dotenv(BACKEND_ROOT / ".env")

VIEW_BASE_URL = os.getenv("VIEW_BASE_URL", "http://localhost:5173").rstrip("/")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))

INSTRUCTIONS = f"""
You help users build DCF (Discounted Cash Flow) valuation models.

SESSION (automatic):
- The server creates and remembers a workspace for this chat connection.
- You do NOT need to call start_session unless the user wants their dashboard link early.
- On the first tool call, a session is created automatically.
- Optional: pass session_id only if the user gave you one from a prior link.

RULES:
- Ask for each required input before calling run_dcf.
- NEVER invent numbers — only pass values the user explicitly stated.
- Do NOT do arithmetic yourself — run_dcf computes everything in Python.
- After any tool call, share view_url so the user can open their dashboard.

Workflow:
  1. (Optional) start_session() → share view_url
  2. Collect assumptions from user
  3. run_dcf(inputs) → model appears on dashboard (session is automatic)
"""

mcp = FastMCP(
    "financial-models",
    instructions=INSTRUCTIONS,
    host=MCP_HOST,
    port=MCP_PORT,
)


def _view_url(session_id: str) -> str:
    return f"{VIEW_BASE_URL}/s/{session_id}"


def _session_response(session_id: str, extra: dict | None = None) -> dict:
    out = {
        "session_id": session_id,
        "view_url": _view_url(session_id),
    }
    if extra:
        out.update(extra)
    return out


@mcp.tool()
def start_session(ctx: Context) -> dict:
    """
    Get or create the workspace for this chat. Returns a private dashboard link.
    Safe to call anytime — reuses the same session for this connection if one exists.
    """
    session_id = resolve_workspace_session(ctx)
    url = _view_url(session_id)
    return {
        "session_id": session_id,
        "view_url": url,
        "message": (
            f"Your workspace is ready. Open {url} to see models and files. "
            "This link stays the same for this chat."
        ),
    }


@mcp.tool()
def run_dcf(
    base_revenue: float,
    revenue_growth: float | list[float],
    ebitda_margin: float,
    tax_rate: float,
    capex_pct: float,
    nwc_pct: float,
    wacc: float,
    terminal_growth: float,
    projection_years: int,
    ctx: Context,
    session_id: str | None = None,
    net_debt: float | None = None,
    shares_outstanding: float | None = None,
    company_name: str | None = None,
) -> dict:
    """
    Build a DCF model from user-provided inputs. Session is created automatically
    for this chat if needed. All amounts in millions USD.
    """
    try:
        sid = resolve_workspace_session(ctx, session_id)
    except ValueError as exc:
        return {"error": str(exc)}

    try:
        inputs = DcfInputs(
            base_revenue=base_revenue,
            revenue_growth=revenue_growth,
            ebitda_margin=ebitda_margin,
            tax_rate=tax_rate,
            capex_pct=capex_pct,
            nwc_pct=nwc_pct,
            wacc=wacc,
            terminal_growth=terminal_growth,
            projection_years=projection_years,
            net_debt=net_debt,
            shares_outstanding=shares_outstanding,
        )
    except ValueError as exc:
        return _session_response(sid, {"error": str(exc)})

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
