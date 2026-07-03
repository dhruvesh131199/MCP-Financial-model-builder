"""Session-scoped model creation API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from store import session_exists

router = APIRouter(prefix="/api/sessions/{session_id}/models", tags=["session-models"])


class DcfCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    projection_years: int = Field(..., ge=1, le=10)
    ticker: str | None = None
    base_revenue: float | None = Field(default=None, ge=0)


class ComparativeCreateBody(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    target: str = Field(..., min_length=1, max_length=120)
    peers: list[str] = Field(..., min_length=1, max_length=5)


def _require_session(session_id: str) -> None:
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/dcf")
def post_create_dcf_model(session_id: str, body: DcfCreateBody) -> dict:
    from services.dcf_service import create_dcf_draft

    _require_session(session_id)
    ticker = body.ticker.strip().upper() if body.ticker and body.ticker.strip() else None

    try:
        result = create_dcf_draft(
            session_id,
            ticker=ticker,
            projection_years=body.projection_years,
            model_name=body.name.strip(),
            base_revenue=body.base_revenue,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        **result,
        "message": (
            f"DCF template '{result['model_name']}' created "
            f"({result['projection_years']}-year forecast). "
            "Fill assumptions in the editor and click Update model."
        ),
    }


@router.post("/comparative")
def post_create_comparative_model(session_id: str, body: ComparativeCreateBody) -> dict:
    from services.comparative import create_comparative_model

    _require_session(session_id)

    try:
        result = create_comparative_model(
            session_id,
            target=body.target.strip(),
            peers=[p.strip() for p in body.peers if p.strip()],
            model_name=body.name.strip() if body.name and body.name.strip() else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result
