"""Session-scoped RAG API — fetch/upload with dedup + chunk reads."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from helper.rag.chunk_ids import ALLOWED_DOCTYPES
from helper.postgres.postgres_read import load_chunk_plan_from_db
from helper.rag.resolve import resolve_or_ingest_sec, resolve_or_ingest_upload
from helper.rag.storage import (
    ensure_session_document_dir,
    find_document_dir,
    load_meta,
    session_document_has_report,
)
from store import session_exists
from rag_session_store import find_rag_document_by_document_id, rag_document_api_urls

router = APIRouter(prefix="/api/sessions/{session_id}/rag", tags=["session-rag"])

_RAW_MEDIA = {
    ".pdf": "application/pdf",
    ".htm": "text/html",
    ".html": "text/html",
}


def _raw_media_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return _RAW_MEDIA.get(ext, "application/octet-stream")


def _document_api_urls(session_id: str, document_id: str) -> dict[str, str]:
    return rag_document_api_urls(session_id, document_id)


def _resolve_session_doc_dir(session_id: str, document_id: str) -> Path:
    out_dir = ensure_session_document_dir(session_id, document_id)
    if out_dir is None:
        raise HTTPException(status_code=404, detail="Document files not found for session")
    return out_dir


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
        from helper.rag.chunk_loader import load_chunk_plan

        plan = load_chunk_plan(out_dir, meta)
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
    from session_process_store import RagIngestProgress

    _require_session(session_id)
    progress = RagIngestProgress.start(session_id, source="rest", n_filings=1)
    try:
        result = resolve_or_ingest_sec(
            session_id=session_id,
            ticker=body.ticker,
            fiscal_year=body.fiscal_year,
            progress=progress,
        )
        progress.finish()
        progress = None  # type: ignore[assignment]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if progress is not None:
            progress.abandon()
    return result.to_dict()


@router.post("/ingest/upload")
async def post_rag_upload(
    session_id: str,
    file: UploadFile = File(...),
    ticker: str = Form(...),
    year: int = Form(...),
    doctype: str = Form(default="10K"),
) -> dict:
    from session_process_store import RagIngestProgress

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

    progress = RagIngestProgress.start(session_id, source="rest", n_filings=1)
    try:
        result = resolve_or_ingest_upload(
            session_id=session_id,
            upload_path=tmp_path,
            original_filename=file.filename or "upload.bin",
            ticker=ticker,
            year=year,
            doctype=normalized,
            progress=progress,
        )
        progress.finish()
        progress = None  # type: ignore[assignment]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)
        if progress is not None:
            progress.abandon()

    return result.to_dict()


@router.get("/documents/{document_id}")
def get_rag_document(session_id: str, document_id: str) -> dict:
    _require_session(session_id)
    entry = find_rag_document_by_document_id(session_id, document_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Document not in session")
    out: dict = {"session_id": session_id, **entry}
    out.update(_document_api_urls(session_id, document_id))
    out["has_report"] = session_document_has_report(session_id, document_id)
    try:
        out_dir = find_document_dir(session_id, document_id)
        meta = load_meta(out_dir)
        out["has_local_files"] = True
        out["markdown_chars"] = meta.get("markdown_chars")
    except FileNotFoundError:
        out["has_local_files"] = False
        out["from_cache_only"] = not out["has_report"]
    return out


@router.get("/documents/{document_id}/chunks")
def get_rag_chunks(session_id: str, document_id: str) -> dict:
    _require_session(session_id)
    entry = find_rag_document_by_document_id(session_id, document_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Document not in session")
    return _load_chunks_for_document(session_id, document_id)


@router.get("/documents/{document_id}/raw")
def get_rag_document_raw(session_id: str, document_id: str) -> FileResponse:
    _require_session(session_id)
    entry = find_rag_document_by_document_id(session_id, document_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Document not in session")
    out_dir = _resolve_session_doc_dir(session_id, document_id)
    meta = load_meta(out_dir)
    raw_name = meta.get("raw_filename")
    if not raw_name:
        raise HTTPException(status_code=404, detail="Raw file not found")
    raw_path = out_dir / raw_name
    if not raw_path.is_file():
        raise HTTPException(status_code=404, detail="Raw file not found")
    return FileResponse(
        path=raw_path,
        media_type=_raw_media_type(raw_name),
        filename=raw_name,
    )


@router.get("/documents/{document_id}/report")
def get_rag_document_report(session_id: str, document_id: str) -> HTMLResponse:
    _require_session(session_id)
    entry = find_rag_document_by_document_id(session_id, document_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Document not in session")
    out_dir = _resolve_session_doc_dir(session_id, document_id)
    report = out_dir / "report.html"
    if not report.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    return HTMLResponse(content=report.read_text(encoding="utf-8"))


@router.get("/parents/{parent_id}")
def get_rag_parent_chunk(session_id: str, parent_id: str) -> dict:
    """Load one parent chunk by id for the citation source drawer.

    Use when: dashboard clicks an inline [[cite:…]] chip.
    Logic: require session → load_parent_chunk from Postgres → add display label.
    Returns: e.g. {"parent_id": "AAPL_2025_10K_P_07", "ticker": "AAPL", "year": 2025,
    "doctype": "10K", "chunk_index": 7, "content": "...", "label": "AAPL · 10K · FY2025 · section #7"}
    """
    _require_session(session_id)
    pid = parent_id.strip()
    if not pid:
        raise HTTPException(status_code=400, detail="parent_id is required")

    from services.rag_vector_search import load_parent_chunk

    try:
        row = load_parent_chunk(pid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if row is None:
        raise HTTPException(status_code=404, detail="Parent chunk not found")

    ticker = str(row.get("ticker") or "")
    doctype = str(row.get("doctype") or "")
    year = row.get("year")
    chunk_index = row.get("chunk_index")
    label = f"{ticker} · {doctype} · FY{year} · section #{chunk_index}"
    return {**row, "label": label}
