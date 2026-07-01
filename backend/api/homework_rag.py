"""Homework RAG lab API — fetch/upload → MarkItDown (Phase 1)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from homework.rag_markitdown.chunk_ids import (
    ALLOWED_DOCTYPES,
    DocumentFilingKey,
    filing_key_from_meta,
)
from homework.rag_markitdown.chunk_plan import build_chunk_plan
from homework.rag_markitdown.pipeline import ingest_from_sec, ingest_from_upload
from homework.rag_markitdown.schema import FilingMeta, SectionOutline
from homework.rag_markitdown.storage import (
    find_document_dir,
    find_homework_document_by_id,
    load_meta,
)
from store import session_exists

router = APIRouter(prefix="/api/homework/rag", tags=["homework-rag"])

_RAW_MEDIA = {
    ".pdf": "application/pdf",
    ".htm": "text/html",
    ".html": "text/html",
}


def _raw_media_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return _RAW_MEDIA.get(ext, "application/octet-stream")


def _filing_key_from_meta(meta: dict) -> DocumentFilingKey:
    cp = meta.get("chunk_plan") or {}
    if cp.get("ticker") and cp.get("year") and cp.get("doctype"):
        return DocumentFilingKey(
            ticker=cp["ticker"],
            year=int(cp["year"]),
            doctype=cp["doctype"],
        )
    filing = meta.get("filing")
    if filing:
        return filing_key_from_meta(FilingMeta.model_validate(filing))
    raise ValueError("Cannot resolve filing key: missing chunk_plan or filing metadata")


def _load_chunk_plan(out_dir: Path, meta: dict) -> dict | None:
    chunks_path = out_dir / "chunks.json"
    if chunks_path.is_file():
        return json.loads(chunks_path.read_text(encoding="utf-8"))
    outline_data = _load_section_outline(out_dir, meta)
    md_path = out_dir / "converted.md"
    if not outline_data or not md_path.is_file():
        return None
    markdown = md_path.read_text(encoding="utf-8", errors="replace")
    outline = SectionOutline.model_validate(outline_data)
    try:
        filing_key = _filing_key_from_meta(meta)
    except ValueError:
        return None
    plan = build_chunk_plan(
        markdown, outline, meta.get("document_id", ""), filing_key
    )
    return plan.model_dump()


def _chunk_summary(meta: dict) -> dict:
    cp = meta.get("chunk_plan") or {}
    return {
        "parent_count": cp.get("parent_count", 0),
        "subchunk_count": cp.get("subchunk_count", 0),
    }


def _load_section_outline(out_dir: Path, meta: dict) -> dict | None:
    if meta.get("section_outline"):
        return meta["section_outline"]
    sections_path = out_dir / "sections.json"
    if sections_path.is_file():
        return json.loads(sections_path.read_text(encoding="utf-8"))
    return None


class FetchAnnualBody(BaseModel):
    ticker: str
    session_id: str | None = None


def _resolve_doc_dir(document_id: str, session_id: str | None) -> Path:
    if session_id:
        if not session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        try:
            return find_document_dir(session_id, document_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Document not found") from None
    out = find_homework_document_by_id(document_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return out


@router.post("/ingest/fetch")
def post_ingest_fetch(body: FetchAnnualBody) -> dict:
    if body.session_id and not session_exists(body.session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        result = ingest_from_sec(
            ticker=body.ticker,
            session_id=body.session_id,
            homework_output=body.session_id is None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None

    return {
        "success": True,
        **result.to_summary_dict(),
        "report_url": f"/api/homework/rag/documents/{result.document_id}/report"
        + (f"?session_id={body.session_id}" if body.session_id else ""),
    }


@router.post("/ingest/upload")
async def post_ingest_upload(
    file: UploadFile = File(...),
    ticker: str = Form(...),
    year: int = Form(...),
    doctype: str = Form(default="10K"),
    session_id: str | None = Form(default=None),
) -> dict:
    if session_id and not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    normalized_doctype = doctype.strip().upper().replace("-", "")
    if normalized_doctype not in ALLOWED_DOCTYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported doctype: {doctype!r}. Allowed: {sorted(ALLOWED_DOCTYPES)}",
        )

    suffix = Path(file.filename or "upload.bin").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        content = await file.read()
        tmp.write(content)

    try:
        result = ingest_from_upload(
            upload_path=tmp_path,
            original_filename=file.filename or "upload.bin",
            ticker=ticker,
            year=year,
            doctype=normalized_doctype,
            session_id=session_id,
            homework_output=session_id is None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return {
        "success": True,
        **result.to_summary_dict(),
        "report_url": f"/api/homework/rag/documents/{result.document_id}/report"
        + (f"?session_id={session_id}" if session_id else ""),
    }


@router.get("/documents/{document_id}")
def get_document(document_id: str, session_id: str | None = None) -> dict:
    out_dir = _resolve_doc_dir(document_id, session_id)
    meta = load_meta(out_dir)
    outline = _load_section_outline(out_dir, meta)
    summary = _chunk_summary(meta)
    return {
        **meta,
        "section_outline": outline,
        "items_found": outline.get("items_found", 0) if outline else 0,
        **summary,
        "markdown_excerpt": "",
        "raw_url": f"/api/homework/rag/documents/{document_id}/raw"
        + (f"?session_id={session_id}" if session_id else ""),
        "chunks_url": f"/api/homework/rag/documents/{document_id}/chunks"
        + (f"?session_id={session_id}" if session_id else ""),
        "report_url": f"/api/homework/rag/documents/{document_id}/report"
        + (f"?session_id={session_id}" if session_id else ""),
    }


@router.get("/documents/{document_id}/chunks")
def get_document_chunks(document_id: str, session_id: str | None = None) -> dict:
    out_dir = _resolve_doc_dir(document_id, session_id)
    meta = load_meta(out_dir)
    plan = _load_chunk_plan(out_dir, meta)
    if plan is None:
        raise HTTPException(status_code=404, detail="Chunks not found")
    return plan


@router.get("/documents/{document_id}/raw")
def get_document_raw(document_id: str, session_id: str | None = None) -> FileResponse:
    out_dir = _resolve_doc_dir(document_id, session_id)
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
def get_document_report(document_id: str, session_id: str | None = None) -> HTMLResponse:
    out_dir = _resolve_doc_dir(document_id, session_id)
    report = out_dir / "report.html"
    if not report.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    return HTMLResponse(content=report.read_text(encoding="utf-8"))
