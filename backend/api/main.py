"""Read-only API for session dashboards."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from store import load_workspace, session_exists

app = FastAPI(title="Financial Model Builder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/sessions/{session_id}")
def get_session_workspace(session_id: str) -> dict:
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    workspace = load_workspace(session_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return workspace


# Backward-compatible alias
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
