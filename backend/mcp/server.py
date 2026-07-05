"""MCP server over HTTP. Anonymous sessions — explicit session_id per tool call."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Annotated, Any

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

from ingest.edgar_identity import ensure_edgar_identity

ensure_edgar_identity()

import importlib
import importlib.util

# Load local app package without registering as `mcp` (pip package uses that name).
_app_mcp_spec = importlib.util.spec_from_file_location(
    "app_mcp",
    BACKEND_ROOT / "mcp" / "__init__.py",
    submodule_search_locations=[str(BACKEND_ROOT / "mcp")],
)
_app_mcp_pkg = importlib.util.module_from_spec(_app_mcp_spec)
_app_mcp_spec.loader.exec_module(_app_mcp_pkg)

# Find the installed mcp package
import site

site_packages = site.getsitepackages()[0]
sys.path.insert(0, site_packages)

# Import the real mcp package directly from site-packages
import importlib.machinery

spec = importlib.machinery.PathFinder().find_spec("mcp", [site_packages])
real_mcp = importlib.util.module_from_spec(spec)
sys.modules["real_mcp"] = real_mcp
spec.loader.exec_module(real_mcp)

spec_server = importlib.machinery.PathFinder().find_spec(
    "mcp.server", [os.path.join(site_packages, "mcp")]
)
real_mcp_server = importlib.util.module_from_spec(spec_server)
sys.modules["real_mcp.server"] = real_mcp_server
spec_server.loader.exec_module(real_mcp_server)

spec_fastmcp = importlib.machinery.PathFinder().find_spec(
    "mcp.server.fastmcp", [os.path.join(site_packages, "mcp", "server")]
)
real_mcp_server_fastmcp = importlib.util.module_from_spec(spec_fastmcp)
sys.modules["real_mcp.server.fastmcp"] = real_mcp_server_fastmcp
spec_fastmcp.loader.exec_module(real_mcp_server_fastmcp)

FastMCP = real_mcp_server_fastmcp.FastMCP

sys.path.pop(0)

sys.modules["mcp"] = _app_mcp_pkg

from pydantic import Field

from services.comparative import run_comparative_analysis_from_mcp
from services.dcf_service import create_dcf_draft
from services.detailed_analysis_service import run_detailed_analysis_for_session
from services.sec_client import resolve_ticker as sec_resolve_ticker
from session_resolve import (
    SESSION_ID_PARAM_DESC,
    require_session,
    start_session_resolve,
)
from store import cleanup_expired_sessions

VIEW_BASE_URL = os.getenv("VIEW_BASE_URL", "http://localhost:5173").rstrip("/")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))

SessionId = Annotated[
    str | None,
    Field(
        default=None,
        description=SESSION_ID_PARAM_DESC,
    ),
]

INSTRUCTIONS = """
You are the AI assistant for a private financial analyzer workspace. You help users with financial modeling, SEC financials, detailed analysis reports, and peer comparative analysis.

<session_management>
CRITICAL: Workspace state is tied to `session_id`. Only `start_session` may create a new workspace.

HUMAN IN THE LOOP (STRICT): Before the first workspace tool in this chat, if you have NO `session_id` from a prior tool response, you MUST ask:
"Do you have an existing session id from your dashboard, or should I create a new workspace?"

Then:
- User pastes UUID (dashboard Session id box or /s/{uuid}) → pass `session_id` on every tool call.
- User wants new workspace → call `start_session()` with no session_id, then use returned `session_id`.
- You already have session_id from a prior tool response this chat → pass it on every call (do not re-ask).

Rules:
- Every tool returns `session_id` at the top level. Extract it from JSON — do not rely on chat memory alone.
- NEVER omit `session_id` on fetch_report, create_dcf_model, run_detailed_analysis, run_comparative_analysis, query_rag, or resolve_ticker.
- Other tools return session_required / session_not_found errors if session_id is missing or invalid — ask the user, do not retry blindly.
</session_management>

<tool_routing>
Map user requests to tools precisely:

1. Detailed Analysis -> `run_detailed_analysis`
If the user asks for "detailed analysis", "in-depth breakdown", or a "curated report", use this tool. (Do NOT use `fetch_report`). This populates the Detailed Analysis sidebar and Trend table.
(e.g., "Analyze AAPL in detail" -> ticker="AAPL", default max_years=5)
For "update trend" / "refresh trend table", call `run_detailed_analysis` again for the same ticker.

2. SEC Data & Financials -> `fetch_report`
If the user asks to "fetch financials", "get statements", or "pull reports":
- HUMAN IN THE LOOP (STRICT): You MUST ask the user: "Do you want structured SEC financial tables (Files panel) or the complete 10-K narrative document (RAG)?" Every time you ask unless they already specified tables vs full 10-K for that request.
- NEVER guess or default the `report_type`. Stop and wait for their answer.
- Map their answer to `report_type="just_financials"` (Tables/statements) or `report_type="full_report"` (Full 10-K document/RAG).

3. DCF Modeling -> `create_dcf_model`
Used to build Discounted Cash Flow models in the dashboard.
- HUMAN IN THE LOOP (STRICT): ALWAYS ask the user: "How many years should the DCF forecast cover?" before creating a model. Ask every time this tool is called.
- NEVER call `create_dcf_model` without explicit `projection_years` from the user (1–10). Do not use a default.
- `create_dcf_model` always fetches 5 years of SEC reference data when a ticker is given (independent of forecast length).
- Do NOT collect DCF financial assumptions in the chat. Tell the user to fill them out directly on the UI dashboard and click 'Update model'.

4. Peer comparison -> `run_comparative_analysis`
If the user asks to compare companies (e.g. "KO vs PEP"), pass target + peers in `values` (1–5 peers).

5. RAG narrative Q&A -> `query_rag`
If the user asks a question that needs **10-K narrative evidence** (risks, MD&A, business description, footnotes):
- Ensure corpus exists first: `fetch_report(report_type="full_report", tickers=[...])` if not already ingested.
- Loop 1: `query_rag(mode="retrieve", ticker="NVDA", query="...")` — **ticker required on first retrieve**.
- Loops 2+: `query_rag(mode="retrieve", query="...")` — ticker reused from session state.
- After each retrieve, **read `new_parent.content`**. If you need more information OR the parent refers to another part of the filing ("see Item 7", "Note 12"), call retrieve again with a **new query**.
- When satisfied, `query_rag(mode="finalize")` → answer from `combined_context` and append **Sources:** line from `citations`.
- `query_rag(mode="reset")` clears state for a new question.
</tool_routing>

<rag_loop_engineering>
HOST-DRIVEN LOOP RETRIEVAL (query_rag):

After each `retrieve`, read the returned parent chunk and ask:
1. Do I have enough to answer the user's question?
2. Does this section refer elsewhere in the filing that I still need?

If YES to either → craft a new search query and call `query_rag(mode="retrieve", query="...")` again.
If NO → call `query_rag(mode="finalize")` and answer using `combined_context`.

EXAMPLE:
User: "What are NVIDIA's supply chain and manufacturing risks in the latest 10-K?"
- Loop 1: retrieve ticker="NVDA" query="NVIDIA supply chain risks 10-K" → read Item 1A parent
- Loop 2: retrieve query="NVIDIA Item 2 properties manufacturing suppliers" (ticker omitted — reused)
- finalize → answer user; end with Sources line from citations

Rules:
- Each loop uses a **new host-authored query** (refined each time).
- Search is **scoped to ticker** (locked on loop 1); already-collected parents are skipped.
- Always pass `session_id`. Never exceed 15 retrieve loops — finalize when exhausted or satisfied.
</rag_loop_engineering>

<rag_citations>
After `finalize`, always end your user-facing answer with a **Sources** line using `citations[].label`:
Sources: NVDA · 10-K · FY2025 · section #7; NVDA · 10-K · FY2025 · section #12

- Keep each reference short (use label only — not parent_id or chunk text).
- You may inline short refs in the body e.g. (NVDA FY2025 §7) when citing a specific fact.
- Only cite sections you actually used in the answer.
</rag_citations>

<universal_rules>
- Share `data.view_url` after EVERY tool call so the user can open their dashboard.
- Python computes all math — never calculate valuations or ratios in prose.
- Never invent numbers or tickers — use only what the user stated or tools returned.
- Always tell the user the next step from the latest tool response `data.message`.
- Workflow details live in each tool's docstring — read the tool you are about to call.
</universal_rules>
"""

mcp = FastMCP(
    "financial-models",
    instructions=INSTRUCTIONS,
    host=MCP_HOST,
    port=MCP_PORT,
)

from mcp.tool_response import SYSTEM_NOTE, tool_response as _tool_response, view_url as _view_url


def _touch_session_writes() -> None:
    cleanup_expired_sessions()


def _require_session_or_error(session_id: str | None) -> str | dict[str, Any]:
    sid, err = require_session(session_id)
    if err:
        return _tool_response(None, err.to_dict())
    return sid


@mcp.tool()
def start_session(session_id: SessionId = None) -> dict:
    """
    Create or attach to a workspace and return the dashboard link.

    SESSION: The ONLY tool that creates a new workspace. Call after the user confirms
    "create a new workspace". Pass session_id to attach an existing dashboard UUID.

    - Omit session_id → create new workspace (after user confirmed new).
    - Pass session_id → attach existing dashboard; errors if not found or invalid.
    """
    sid, reused, err = start_session_resolve(session_id)
    if err:
        return _tool_response(None, err.to_dict())

    _touch_session_writes()
    url = _view_url(sid)
    return _tool_response(
        sid,
        {
            "created_new": not reused,
            "reused_existing": reused,
            "message": (
                f"Workspace {'linked' if reused else 'ready'}. Open your dashboard: {url} "
                "What would you like to do — build a DCF, fetch SEC financials (Files), "
                "run detailed analysis (Detailed Analysis report), or run a peer comparison?"
            ),
        },
    )


@mcp.tool()
def create_dcf_model(
    projection_years: int,
    ticker: str | None = None,
    company_name: str | None = None,
    model_name: str | None = None,
    base_revenue: float | None = None,
    session_id: SessionId = None,
) -> dict:
    """
    Create a DCF model template on the dashboard. REQUIRED before any DCF valuation.

    WORKFLOW:
    1. Ask the user how many forecast years (projection_years) they want — required, no default! Strictly: Always ask when the tool is called.
    2. Example:create_dcf_model(projection_years=5, ticker="MU") — fetches 5Y SEC reference when ticker given.
    3. User opens view_url → fills WACC, terminal g, base revenue, per-year rows → Update model.

    RULES:
    - projection_years is REQUIRED (1–10). Never omit or guess. Strictly: Always ask when the tool is called.
    - ticker is optional — omit for blank template (user enters base revenue manually).
    - SEC fetch is always 5 years for reference history when ticker provided.
    - base_revenue ($M) optional — overrides SEC prefill when ticker given.
    - Strictly: Do NOT collect DCF assumptions in chat — dashboard editor only.

    SESSION: session_id REQUIRED — from prior tool response or user-pasted dashboard id.
    """
    session_result = _require_session_or_error(session_id)
    if isinstance(session_result, dict):
        return session_result
    sid = session_result

    if not ticker and not company_name and not model_name:
        return _tool_response(
            sid,
            {"error": "Provide ticker, company_name, or model_name for the template"},
        )

    _touch_session_writes()
    result = create_dcf_draft(
        sid,
        ticker=ticker,
        company_name=company_name,
        projection_years=projection_years,
        model_name=model_name,
        base_revenue=base_revenue,
    )
    if "error" in result:
        return _tool_response(sid, result)

    url = _view_url(sid)
    n = result.get("projection_years")
    ref = result.get("reference_years", 0)
    ref_note = f", {ref}-year SEC reference" if ref else ", no SEC reference"
    return _tool_response(
        sid,
        {
            **result,
            "message": (
                f"DCF draft created ({n}-year forecast{ref_note}). "
                f"Open {url} → fill assumptions in the editor → click Update model."
            ),
        },
    )


@mcp.tool()
def resolve_ticker(
    company_name: str | None = None,
    ticker: str | None = None,
    session_id: SessionId = None,
) -> dict:
    """
    Resolve a US public company name or ticker symbol to SEC listing metadata.
    Use when the user says a company name (e.g. "Apple", "Tesla") and you need the ticker.
    At least one of company_name or ticker is required.

    SESSION: session_id REQUIRED — from prior tool response or user-pasted dashboard id.
    """
    session_result = _require_session_or_error(session_id)
    if isinstance(session_result, dict):
        return session_result
    sid = session_result

    result = sec_resolve_ticker(company_name=company_name, ticker=ticker)
    if "error" in result:
        return _tool_response(sid, result)
    return _tool_response(
        sid,
        {
            **result,
            "message": (
                f"Resolved {result['entity_name']} as {result['ticker']} "
                f"(CIK {result['cik']})."
            ),
        },
    )


sys.modules["mcp.server"] = sys.modules[__name__]
from mcp.fetch_report import run_fetch_report


@mcp.tool()
def fetch_report(
    report_type: str,
    tickers: list[str],
    years: list[int] | None = None,
    max_years: int = 1,
    session_id: SessionId = None,
) -> dict:
    """
    Fetch financial reports for one or more US public companies.

    REQUIRED DISAMBIGUATION:
    If report_type is unclear, Strictly ALWAYS ask when the tool is called: "Do you want structured SEC financial tables (Files panel) or the complete 10-K narrative document (RAG)?"

    report_type MUST be one of:
    - "just_financials": Structured XBRL tables (income/balance/cashflow) in Files panel. Use for DCF, comps, or raw data browsing.
    - "full_report": Entire filed 10-K document as markdown (narrative, risk factors, MD&A, footnotes) for RAG. Saves to RAG sidebar.

    USER PHRASE → CALL EXAMPLES:
    | User says | Call |
    | "Fetch Apple financial statements" / tables for Files | report_type="just_financials", tickers=["AAPL"] |
    | "Fetch Apple annual report" / full 10-K for RAG | report_type="full_report", tickers=["AAPL"] |
    | "Fetch Walmart 2024 annual report" | report_type="full_report", tickers=["WMT"], years=[2024] |
    | "Last 5 years for AAPL and MSFT" | report_type="just_financials", tickers=["AAPL", "MSFT"], max_years=5 |

    YEAR RESOLUTION:
    - years=[2024] → Fetch FY2024 only
    - years=[2023, 2024] → Fetch each listed year
    - years omitted, max_years=N → Last N distinct fiscal years
    - years omitted, max_years=1 (default) → Latest filing only

    SESSION: session_id REQUIRED — from prior tool response or user-pasted dashboard id.
    """
    session_result = _require_session_or_error(session_id)
    if isinstance(session_result, dict):
        return session_result
    sid = session_result
    _touch_session_writes()

    from typing import cast

    from mcp.fetch_report import ReportType

    return _tool_response(
        sid,
        run_fetch_report(
            session_id=sid,
            report_type=cast(ReportType, report_type),
            tickers=tickers,
            years=years,
            max_years=max_years,
        ),
    )


@mcp.tool()
def run_detailed_analysis(
    company_name: str | None = None,
    ticker: str | None = None,
    fiscal_years: list[int] | None = None,
    max_years: int = 5,
    session_id: SessionId = None,
) -> dict:
    """
    Build curated Detailed Analysis report for a US public company (5-year default).

    **Use this tool when the user asks for detailed analysis** — not fetch_report.
    Saves to the dashboard **Detailed Analysis** sidebar: income, balance, and cash flow
    sections in one scrollable report with derived metrics, integrity checks, and a
    **Trend analysis** table (revenue, margins, EPS, YoY growth).

    Uses session statements cache (ticker → period → statement). Fetches only missing
    income/balance/cashflow leaves, syncs Files, then saves type=detailed_analysis.

    USER PHRASE → CALL (always this tool, never fetch_report):
    | User says | Call |
    | "Detailed analysis for Apple" | run_detailed_analysis(ticker="AAPL") |
    | "Do a detailed analysis on AAPL" | run_detailed_analysis(ticker="AAPL") |
    | "Analyze Microsoft in detail" | run_detailed_analysis(company_name="Microsoft") |
    | "Detailed analysis last 3 years" | run_detailed_analysis(ticker="...", max_years=3) |
    | "Detailed analysis for FY2023" | run_detailed_analysis(ticker="...", fiscal_years=[2023]) |

    Pass session_id from your previous tool response on every call in the same workspace.

    For partial raw SEC data only (Files panel), use fetch_report(just_financials).
    Repeat calls skip SEC fetch when cache is complete (statements_cached=true).

    TREND TABLE: included automatically. To refresh trend only, call this tool again for the ticker.

    SESSION: session_id REQUIRED — from prior tool response or user-pasted dashboard id.
    """
    session_result = _require_session_or_error(session_id)
    if isinstance(session_result, dict):
        return session_result
    sid = session_result

    if not company_name and not ticker:
        return _tool_response(sid, {"error": "Provide company_name or ticker"})

    _touch_session_writes()
    result = run_detailed_analysis_for_session(
        sid,
        company_name=company_name,
        ticker=ticker,
        fiscal_years=fiscal_years,
        max_years=max_years,
    )
    if "error" in result:
        return _tool_response(sid, result)

    url = _view_url(sid)
    return _tool_response(
        sid,
        {
            **result,
            "message": (
                f"Detailed Analysis saved for {result.get('ticker')}. "
                f"{result.get('periods_count', 0)} periods. "
                f"Open {url} → Detailed Analysis sidebar."
            ),
        },
    )


@mcp.tool()
def run_comparative_analysis(
    values: dict[str, Any] | None = None,
    model_name: str | None = None,
    session_id: SessionId = None,
) -> dict:
    """
    Build a peer comparison report (target + 1–5 peers) in one call.

    Pass `values` with target and peers on first use. Omit `values` to rerun from session inputs.
    Pass session_id from your previous tool response on every call in the same workspace.

    VALUES (all optional on repeat calls):
    - values.target: {{ticker, company_name?}}
    - values.peers: list of {{ticker, company_name?}} (1–5)
    - values.fiscal_year: optional int — same FY for all; omit for each company's latest annual FY
    - values.link: {{ticker, file_id}} when Files already exist
    - model_name: optional display name (default "{target} vs {peer1} vs …" from tickers on full create)

    Auto-fetches last 2 annual SEC years per ticker when cache gaps exist (YoY revenue growth),
    links by ticker, fetches Finnhub market data, and builds the comparative report.

    SESSION: session_id REQUIRED — from prior tool response or user-pasted dashboard id.
    """
    session_result = _require_session_or_error(session_id)
    if isinstance(session_result, dict):
        return session_result
    sid = session_result
    _touch_session_writes()
    result = run_comparative_analysis_from_mcp(sid, values=values, model_name=model_name)
    return _tool_response(sid, result)


sys.modules["mcp.server"] = sys.modules[__name__]
from mcp.query_rag import run_query_rag


@mcp.tool()
def query_rag(
    mode: str,
    query: str | None = None,
    ticker: str | None = None,
    original_question: str | None = None,
    top_k: int = 10,
    session_id: SessionId = None,
) -> dict:
    """
    Loop RAG retrieval over Postgres 10-K corpus — host-driven, max 15 loops.

    Returns parent chunk sections (with full metadata) for the host to read and decide
    whether to retrieve again or finalize. Python does NOT generate the final answer.

    MODES:
    - retrieve: embed query → ticker-scoped pgvector top-10 → HF rerank → return best unseen parent
    - finalize: merge deduped parent texts → combined_context + citations for host to answer
    - reset: clear session rag_query_state.json

    TICKER (retrieve):
    - Loop 1: ticker REQUIRED (e.g. NVDA) — locks scope for this run
    - Loops 2+: omit ticker (reused from state); do not pass a different ticker

    LOOP ENGINEERING (host responsibility):
    After each retrieve, read `new_parent.content`. If you need more information OR the
    parent refers to another part of the filing, call retrieve again with a NEW query.
    When satisfied, call finalize.

    CITATIONS: After finalize, end your answer with Sources: using citations[].label

    USER PHRASE → CALL:
    | User says | Call |
    | "What are NVDA supply chain risks in the 10-K?" | retrieve ticker="NVDA" query="NVDA supply chain risks 10-K" |
    | Parent cites Item 2 | retrieve query="NVDA Item 2 manufacturing suppliers 10-K" |
    | Enough context gathered | finalize |
    | New unrelated question | reset then retrieve with new ticker |

    PREREQUISITE: ingest 10-Ks via fetch_report(report_type="full_report") so Postgres has embeddings.

    PARAMETERS:
    - mode: required — retrieve | finalize | reset
    - query: required on retrieve — host-crafted search query for THIS loop
    - ticker: required on loop 1 retrieve only
    - original_question: optional on loop 1 — user's verbatim question (stored for finalize)
    - top_k: sub-chunks per loop (default 10)
    - session_id: REQUIRED — from prior tool response or user-pasted dashboard id
    """
    session_result = _require_session_or_error(session_id)
    if isinstance(session_result, dict):
        return session_result
    sid = session_result
    _touch_session_writes()

    from typing import cast

    from mcp.query_rag import QueryRagMode

    normalized = mode.strip().lower()
    if normalized not in ("retrieve", "finalize", "reset"):
        return _tool_response(
            sid,
            {"error": f"Invalid mode {mode!r}. Use retrieve, finalize, or reset."},
        )

    result = run_query_rag(
        mode=cast(QueryRagMode, normalized),
        session_id=sid,
        query=query,
        ticker=ticker,
        original_question=original_question,
        top_k=top_k,
    )
    return _tool_response(sid, result)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
