"""Session-scoped RAG API — fetch/upload with dedup + chunk reads."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from homework.rag_markitdown.chunk_ids import ALLOWED_DOCTYPES
from homework.rag_markitdown.postgres_read import load_chunk_plan_from_db
from homework.rag_markitdown.resolve import resolve_or_ingest_sec, resolve_or_ingest_upload
from homework.rag_markitdown.storage import find_document_dir, load_meta
from store import session_exists
from rag_session_store import find_rag_document, find_rag_document_by_document_id

router = APIRouter(prefix="/api/sessions/{session_id}/rag", tags=["session-rag"])


class RagFetchBody(BaseModel):
    ticker: str
    fiscal_year: int | None = None


def _require_session(session_id: str) -> None:
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")


def _load_chunks_for_document(session_id: str, document_id: str) -> dict:
    try:
        out_dir = find_document_dir(session_id, document_id)
        chunks_path = out_dir / "chunks.json"
        if chunks_path.is_file():
            return json.loads(chunks_path.read_text(encoding="utf-8"))
        meta = load_meta(out_dir)
        from api.homework_rag import _load_chunk_plan

        plan = _load_chunk_plan(out_dir, meta)
        if plan:
            return plan
    except FileNotFoundError:
        pass

    plan = load_chunk_plan_from_db(document_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Chunks not found")
    return plan.model_dump()


@router.post("/ingest/fetch")
def post_rag_fetch(session_id: str, body: RagFetchBody) -> dict:
    _require_session(session_id)
    try:
        result = resolve_or_ingest_sec(
            session_id=session_id,
            ticker=body.ticker,
            fiscal_year=body.fiscal_year,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.to_dict()


@router.post("/ingest/upload")
async def post_rag_upload(
    session_id: str,
    file: UploadFile = File(...),
    ticker: str = Form(...),
    year: int = Form(...),
    doctype: str = Form(default="10K"),
) -> dict:
    _require_session(session_id)
    normalized = doctype.strip().upper().replace("-", "")
    if normalized not in ALLOWED_DOCTYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported doctype: {doctype!r}",
        )

    suffix = Path(file.filename or "upload.bin").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        content = await file.read()
        tmp.write(content)

    try:
        result = resolve_or_ingest_upload(
            session_id=session_id,
            upload_path=tmp_path,
            original_filename=file.filename or "upload.bin",
            ticker=ticker,
            year=year,
            doctype=normalized,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return result.to_dict()


@router.get("/documents/{document_id}")
def get_rag_document(session_id: str, document_id: str) -> dict:
    _require_session(session_id)
    entry = find_rag_document_by_document_id(session_id, document_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Document not in session")
    out: dict = {"session_id": session_id, **entry}
    try:
        out_dir = find_document_dir(session_id, document_id)
        meta = load_meta(out_dir)
        out["has_local_files"] = True
        out["markdown_chars"] = meta.get("markdown_chars")
        out["report_url"] = (
            f"/api/sessions/{session_id}/rag/documents/{document_id}/report"
        )
        out["raw_url"] = (
            f"/api/sessions/{session_id}/rag/documents/{document_id}/raw"
        )
    except FileNotFoundError:
        out["has_local_files"] = False
        out["from_cache_only"] = True
    out["chunks_url"] = (
        f"/api/sessions/{session_id}/rag/documents/{document_id}/chunks"
    )
    return out


@router.get("/documents/{document_id}/chunks")
def get_rag_chunks(session_id: str, document_id: str) -> dict:
    _require_session(session_id)
    entry = find_rag_document_by_document_id(session_id, document_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Document not in session")
    return _load_chunks_for_document(session_id, document_id)
