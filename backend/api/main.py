"""Read-only API for session dashboards."""

import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from store import cleanup_expired_sessions, load_workspace, session_exists

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
    allow_methods=["GET"],
    allow_headers=["*"],
)


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
