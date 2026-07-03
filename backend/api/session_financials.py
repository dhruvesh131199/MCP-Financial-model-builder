"""Session-scoped structured SEC financials fetch API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from store import append_financials_fetch_log, session_exists

router = APIRouter(prefix="/api/sessions/{session_id}/financials", tags=["session-financials"])

MAX_TICKERS = 5
MAX_YEARS = 10


class FinancialsFetchBody(BaseModel):
    tickers: list[str] = Field(..., min_length=1, max_length=MAX_TICKERS)
    years: list[int] | None = Field(default=None, max_length=MAX_YEARS)
    max_years: int | None = Field(default=None, ge=1, le=10)


def _require_session(session_id: str) -> None:
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")


def _normalize_tickers(tickers: list[str]) -> list[str]:
    clean = [t.strip().upper() for t in tickers if t and t.strip()]
    if not clean:
        raise HTTPException(status_code=400, detail="At least one valid ticker is required.")
    if len(clean) > MAX_TICKERS:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_TICKERS} tickers allowed.")
    return clean


def _normalize_years(years: list[int] | None) -> list[int] | None:
    if not years:
        return None
    if len(years) > MAX_YEARS:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_YEARS} fiscal years allowed.")
    return years


def _resolve_max_years(years: list[int] | None, max_years: int | None) -> int:
    if years:
        return 1
    if max_years is not None:
        return max_years
    return 1


def _derive_status(results: list[dict]) -> str:
    if not results:
        return "error"
    successes = sum(1 for r in results if r.get("success"))
    if successes == len(results):
        return "success"
    if successes == 0:
        return "error"
    return "partial"


@router.post("/fetch")
def post_financials_fetch(session_id: str, body: FinancialsFetchBody) -> dict:
    from services.financials_fetch_service import run_session_financials_fetch

    _require_session(session_id)
    tickers = _normalize_tickers(body.tickers)
    years = _normalize_years(body.years)
    resolved_max_years = _resolve_max_years(years, body.max_years)

    fetch_result = run_session_financials_fetch(
        session_id,
        tickers=tickers,
        years=years,
        max_years=resolved_max_years,
    )

    if "error" in fetch_result and not fetch_result.get("results"):
        raise HTTPException(status_code=400, detail=fetch_result["error"])

    results = fetch_result.get("results") or []
    status = _derive_status(results)
    request_id = str(uuid.uuid4())
    success_count = sum(1 for r in results if r.get("success"))
    total_count = len(results)

    log_entry = append_financials_fetch_log(
        session_id,
        {
            "id": request_id,
            "source": "rest",
            "tickers": tickers,
            "years": years,
            "max_years": None if years else resolved_max_years,
            "status": status,
            "results": results,
            "errors": fetch_result.get("errors") or [],
        },
    )

    return {
        "request_id": log_entry["id"],
        "tickers": tickers,
        "years": years,
        "max_years": None if years else resolved_max_years,
        "status": status,
        "success_count": success_count,
        "total_count": total_count,
        "results": results,
        "errors": fetch_result.get("errors") or [],
        "message": fetch_result.get("message"),
    }
