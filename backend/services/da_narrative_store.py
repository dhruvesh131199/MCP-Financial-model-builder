"""Detailed Analysis narrative sections — session markdown on disk."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from store import (
    RAG_DISPLAY_CONTENT_MAX_BYTES,
    _session_dir,
    _utc_now,
    find_detailed_analysis_by_ticker,
)

# Ordered UI / playbook sections
DA_NARRATIVE_SECTIONS: tuple[tuple[str, str], ...] = (
    ("gross_profit", "Gross profit analysis"),
    ("return_on_capital", "Return on capital analysis"),
    ("earnings_per_share", "Earnings per share analysis"),
    ("cash_flow", "Cash flow analysis"),
)

DA_NARRATIVE_SECTION_KEYS = frozenset(k for k, _ in DA_NARRATIVE_SECTIONS)
DA_NARRATIVE_TITLES = dict(DA_NARRATIVE_SECTIONS)


def _ticker_dir(session_id: str, ticker: str) -> Path:
    return _session_dir(session_id) / "detailed_analysis" / ticker.strip().upper()


def section_content_path(session_id: str, ticker: str, section_key: str) -> Path:
    return _ticker_dir(session_id, ticker) / section_key / "content.md"


def build_narrative_playbook(ticker: str) -> list[dict[str, str]]:
    """Structured playbook rows for run_detailed_analysis (tasks 2–5)."""
    sym = ticker.strip().upper()
    queries = {
        "gross_profit": (
            f"Reasons behind the change in gross profit and its trend from the "
            f"Business, Risk Factors, and MD&A sections of the {sym} 10-K"
        ),
        "return_on_capital": (
            f"Reasons behind the change in return on capital and its trend from the "
            f"Business, Risk Factors, and MD&A sections of the {sym} 10-K"
        ),
        "earnings_per_share": (
            f"Reasons behind the change in earnings per share and its trend from the "
            f"Business, Risk Factors, and MD&A sections of the {sym} 10-K"
        ),
        "cash_flow": (
            f"Reasons behind the change in cash flow and free cash flow and their "
            f"trends from the Business, Risk Factors, and MD&A sections of the {sym} 10-K"
        ),
    }
    return [
        {
            "section_key": key,
            "title": title,
            "suggested_query": queries[key],
        }
        for key, title in DA_NARRATIVE_SECTIONS
    ]


def build_narrative_next_actions(ticker: str) -> list[str]:
    """Human-readable checklist (tasks 1–5) for the host after DA tables."""
    sym = ticker.strip().upper()
    playbook = build_narrative_playbook(sym)
    actions = [
        (
            f"1. Fetch the full 10-K: fetch_report(report_type=\"full_report\", "
            f"tickers=[\"{sym}\"]) — skip only if this ticker's 10-K is already "
            f"in the session RAG corpus."
        ),
    ]
    for i, row in enumerate(playbook, start=2):
        actions.append(
            f"{i}. Use query_rag (retrieve/finalize) with query: "
            f"\"{row['suggested_query']}\". Then pin with "
            f"rag_res_on_display(destination=\"detailed_analysis\", "
            f"ticker=\"{sym}\", section_key=\"{row['section_key']}\", "
            f"name=\"{row['title']}\", content=<markdown answer with Sources>)."
        )
    return actions


def save_da_narrative(
    session_id: str,
    ticker: str,
    section_key: str,
    content_md: str,
) -> dict[str, Any]:
    """Write narrative markdown for one DA section.

    Use when: rag_res_on_display(destination=detailed_analysis).
    Logic: validate section → require DA model for ticker → write content.md.
    Returns: e.g. {"success": True, "ticker": "AAPL", "section_key": "gross_profit", ...}
    """
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        raise KeyError("Session not found")

    key = section_key.strip().lower()
    if key not in DA_NARRATIVE_SECTION_KEYS:
        raise ValueError(
            f"Invalid section_key={section_key!r}. "
            f"Use one of: {', '.join(sorted(DA_NARRATIVE_SECTION_KEYS))}."
        )

    sym = ticker.strip().upper()
    if not sym:
        raise ValueError("ticker is required for detailed_analysis destination")

    if find_detailed_analysis_by_ticker(session_id, sym) is None:
        raise ValueError(
            f"No Detailed Analysis model for {sym}. "
            "Run run_detailed_analysis for this ticker first."
        )

    body = content_md.strip()
    if not body:
        raise ValueError("content is required")
    if len(body.encode("utf-8")) > RAG_DISPLAY_CONTENT_MAX_BYTES:
        raise ValueError(
            f"content exceeds maximum size ({RAG_DISPLAY_CONTENT_MAX_BYTES // 1024} KB)"
        )

    path = section_content_path(session_id, sym, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")

    # Bump session activity so workspace poll sees a change
    meta = session_dir / "meta.json"
    if meta.exists():
        meta.touch()

    return {
        "success": True,
        "ticker": sym,
        "section_key": key,
        "title": DA_NARRATIVE_TITLES[key],
        "path": str(path.relative_to(session_dir)),
        "updated_at": _utc_now(),
    }


def list_da_narratives(session_id: str, ticker: str) -> list[dict[str, str]]:
    """Return existing narrative sections in fixed UI order."""
    session_dir = _session_dir(session_id)
    if not session_dir.is_dir():
        return []

    sym = ticker.strip().upper()
    out: list[dict[str, str]] = []
    for key, title in DA_NARRATIVE_SECTIONS:
        path = section_content_path(session_id, sym, key)
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            continue
        out.append(
            {
                "section_key": key,
                "title": title,
                "content_md": content,
            }
        )
    return out


def da_narratives_mtime(session_id: str) -> str | None:
    """Latest mtime under detailed_analysis/ for workspace updated_at."""
    from datetime import datetime, timezone

    root = _session_dir(session_id) / "detailed_analysis"
    if not root.is_dir():
        return None
    latest: float | None = None
    for path in root.rglob("content.md"):
        try:
            m = path.stat().st_mtime
        except OSError:
            continue
        if latest is None or m > latest:
            latest = m
    if latest is None:
        return None
    return datetime.fromtimestamp(latest, tz=timezone.utc).isoformat()
