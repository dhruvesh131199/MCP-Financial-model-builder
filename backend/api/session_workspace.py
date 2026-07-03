"""DELETE endpoints for session workspace files and models."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from store import delete_file_entry, delete_model_entry, session_exists

router = APIRouter(prefix="/api/sessions/{session_id}", tags=["session-workspace"])


def _require_session(session_id: str) -> None:
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")


@router.delete("/files/{file_id}")
def delete_session_file(session_id: str, file_id: str) -> dict:
    _require_session(session_id)
    try:
        deleted = delete_file_entry(session_id, file_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")
    return {"success": True, "file_id": file_id}


@router.delete("/models/{model_id}")
def delete_session_model(session_id: str, model_id: str) -> dict:
    _require_session(session_id)
    try:
        deleted = delete_model_entry(session_id, model_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    if not deleted:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"success": True, "model_id": model_id}
