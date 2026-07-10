"""Orchestrator for structured SEC financials fetch (REST + shared with MCP)."""

from __future__ import annotations

from services.sec_fetch_handler import handle_cached_sec_fetch
from session_process_store import delete_process, upsert_process

ALL_STATEMENTS = ["income", "balance", "cashflow"]


def run_session_financials_fetch(
    session_id: str,
    *,
    tickers: list[str],
    years: list[int] | None = None,
    max_years: int = 1,
) -> dict:
    if not tickers:
        return {"error": "tickers list cannot be empty."}

    clean_tickers = [t.strip().upper() for t in tickers if t.strip()]
    if not clean_tickers:
        return {"error": "tickers list must contain valid ticker strings."}

    clamped_max_years = max(1, min(10, max_years))

    results: list[dict] = []
    errors: list[str] = []

    process_id = None
    progress = 2.0
    step = 98.0 / max(1, len(clean_tickers))
    try:
        created = upsert_process(
            session_id,
            source="rest",
            process_name="Fetching SEC files",
            message="Starting…",
            progress=progress,
        )
        process_id = created["id"]
        for i, ticker in enumerate(clean_tickers):
            if i > 0:
                progress = min(100.0, progress + step)
            upsert_process(
                session_id,
                process_id,
                source="rest",
                process_name="Fetching SEC files",
                message=f"Fetching {ticker} data…",
                progress=progress,
            )
            result = handle_cached_sec_fetch(
                session_id,
                company_name=None,
                ticker=ticker,
                fiscal_years=years,
                max_years=clamped_max_years,
                include_annual=True,
                include_quarterly=False,
                statements=ALL_STATEMENTS,
            )
            if "error" in result:
                errors.append(f"{ticker}: {result['error']}")
                results.append(
                    {"ticker": ticker, "success": False, "error": result["error"]}
                )
            else:
                results.append(
                    {
                        "ticker": ticker,
                        "success": True,
                        "file_id": result.get("file_id"),
                        "scope_applied": result.get("scope_applied"),
                    }
                )
        upsert_process(
            session_id,
            process_id,
            source="rest",
            process_name="Fetching SEC files",
            message="Done…",
            progress=100,
        )
    finally:
        if process_id is not None:
            delete_process(session_id, process_id)

    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)

    return {
        "success": len(errors) == 0 and success_count > 0,
        "results": results,
        "errors": errors,
        "message": f"Fetched {success_count}/{total_count} requested reports.",
    }
