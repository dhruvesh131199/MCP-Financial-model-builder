"""Read-only API for session dashboards + DCF draft write endpoints."""

import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.homework_rag import router as homework_rag_router
from api.session_financials import router as session_financials_router
from api.session_models import router as session_models_router
from api.session_rag import router as session_rag_router
from api.session_workspace import router as session_workspace_router
from services.dcf_service import (
    compute_dcf_from_draft,
    preview_dcf_from_draft,
    summarize_dcf_draft,
    update_dcf_draft,
)
from store import (
    cleanup_expired_sessions,
    get_model_entry,
    load_workspace,
    mark_session_guide_seen,
    session_exists,
)

load_dotenv()

CLEANUP_INTERVAL_SECONDS = 600


async def _session_cleanup_loop() -> None:
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        cleanup_expired_sessions()


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_expired_sessions()
    task = asyncio.create_task(_session_cleanup_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Financial Model Builder API", lifespan=lifespan)


def _cors_origins() -> list[str]:
    origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
    if base := os.getenv("VIEW_BASE_URL", "").strip().rstrip("/"):
        origins.append(base)
    if extra := os.getenv("CORS_ORIGINS", "").strip():
        origins.extend(item.strip().rstrip("/") for item in extra.split(",") if item.strip())
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["GET", "PATCH", "POST", "DELETE"],
    allow_headers=["*"],
)


class DcfDraftPatchBody(BaseModel):
    base_revenue: float | None = None
    wacc: float | None = None
    terminal_growth: float | None = None
    net_debt: float | None = None
    shares_outstanding: float | None = None
    revenue_growth: list[float | None] | None = None
    ebitda_margin: list[float | None] | None = None
    tax_rate: list[float | None] | None = None
    capex_pct: list[float | None] | None = None
    nwc_pct: list[float | None] | None = None
    defaults: dict[str, float | None] | None = None


app.include_router(homework_rag_router)
app.include_router(session_rag_router)
app.include_router(session_financials_router)
app.include_router(session_models_router)
app.include_router(session_workspace_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/sessions/{session_id}")
def get_session_workspace(session_id: str) -> dict:
    cleanup_expired_sessions()
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    workspace = load_workspace(session_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return workspace


@app.post("/api/sessions/{session_id}/guide-seen")
def post_session_guide_seen(session_id: str) -> dict:
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        mark_session_guide_seen(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"session_id": session_id, "guide_seen": True}


@app.get("/api/sessions/{session_id}/model")
def get_session_model_legacy(session_id: str) -> dict:
    workspace = get_session_workspace(session_id)
    models = workspace.get("models") or []
    latest = models[-1]["data"] if models else None
    return {
        "session_id": session_id,
        "updated_at": workspace.get("updated_at"),
        "model": latest,
        "exists": True,
    }


def _require_dcf_draft(session_id: str, model_id: str) -> dict:
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    entry = get_model_entry(session_id, model_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Model not found")
    if entry.get("type") != "dcf_draft":
        raise HTTPException(status_code=400, detail="Model is not a DCF draft")
    return entry


@app.patch("/api/sessions/{session_id}/models/{model_id}/dcf-draft")
def patch_dcf_draft(session_id: str, model_id: str, body: DcfDraftPatchBody) -> dict:
    _require_dcf_draft(session_id, model_id)
    payload = body.model_dump(exclude_none=True)
    try:
        result = update_dcf_draft(session_id, model_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Model not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@app.post("/api/sessions/{session_id}/models/{model_id}/dcf-compute")
def post_dcf_compute(session_id: str, model_id: str) -> dict:
    _require_dcf_draft(session_id, model_id)
    try:
        return compute_dcf_from_draft(session_id, model_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Model not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/models/{model_id}/dcf-preview")
def post_dcf_preview(session_id: str, model_id: str) -> dict:
    _require_dcf_draft(session_id, model_id)
    try:
        return preview_dcf_from_draft(session_id, model_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Model not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
