"""Single entry: raw file → MarkItDown → saved artifacts."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from helper.rag.chunk_ids import DocumentFilingKey, filing_key_from_meta
from helper.rag.chunk_plan import build_chunk_plan, chunk_plan_summary
from helper.rag.convert import convert_file_to_markdown, markdown_stats
from helper.rag.fetch_annual import fetch_latest_annual_report
from helper.rag.report_html import build_report_html
from helper.rag.section_analyze import analyze_sections
from helper.rag.schema import (
    DocumentSource,
    FilingMeta,
    IngestResult,
    SourceFormat,
)
from helper.rag.storage import allocate_output_dir, write_meta
from helper.rag.vector_store import VectorStore, get_vector_store

if TYPE_CHECKING:
    from session_process_store import RagIngestProgress

NARRATIVE_MARKERS = (
    ("risk_factors", "risk factors"),
    ("md_and_a", "management"),
    ("financial_statements", "financial statements"),
)

_SEC_FETCH_CONCURRENCY = max(1, int(os.getenv("SEC_FETCH_CONCURRENCY", "4")))
SEC_FETCH_SEMAPHORE = asyncio.Semaphore(_SEC_FETCH_CONCURRENCY)


def _narrative_checks(markdown: str) -> dict[str, bool]:
    lower = markdown.lower()
    return {key: phrase in lower for key, phrase in NARRATIVE_MARKERS}


def _ext_to_format(path: Path) -> SourceFormat:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return SourceFormat.PDF
    if ext in {".htm", ".html"}:
        return SourceFormat.HTML
    return SourceFormat.OTHER


def _finalize_ingest(
    *,
    document_id: str,
    out_dir: Path,
    raw_path: Path,
    source: DocumentSource,
    source_format: SourceFormat,
    filing: FilingMeta | None,
    filing_key: DocumentFilingKey,
    session_id: str | None,
    vector_store: VectorStore,
    defer_vector_ingest: bool = False,
    progress: RagIngestProgress | None = None,
    progress_label: str = "",
) -> IngestResult:
    label = progress_label or filing_key.ticker
    if progress:
        progress.report(f"{label}: converting to markdown")
    markdown = convert_file_to_markdown(raw_path)
    md_path = out_dir / "converted.md"
    md_path.write_text(markdown, encoding="utf-8")
    chars, lines = markdown_stats(markdown)
    if progress:
        progress.report(f"{label}: markdown done", advance_steps=1)

    outline = analyze_sections(markdown)
    sections_path = out_dir / "sections.json"
    sections_path.write_text(
        json.dumps(outline.model_dump(), indent=2), encoding="utf-8"
    )
    if progress:
        progress.report(f"{label}: chunking")
    chunk_plan = build_chunk_plan(markdown, outline, document_id, filing_key)
    chunks_path = out_dir / "chunks.json"
    chunks_path.write_text(
        json.dumps(chunk_plan.model_dump(), indent=2), encoding="utf-8"
    )
    if progress:
        progress.report(
            f"{label}: {chunk_plan.parent_count} parents, "
            f"{chunk_plan.subchunk_count} subchunks",
            advance_steps=1,
        )

    meta_payload = {
        "document_id": document_id,
        "source": source.value,
        "source_format": source_format.value,
        "raw_filename": raw_path.name,
        "raw_bytes": raw_path.stat().st_size,
        "markdown_chars": chars,
        "markdown_lines": lines,
        "filing": filing.model_dump() if filing else None,
        "session_id": session_id,
        "narrative_checks": _narrative_checks(markdown),
        "section_outline": outline.model_dump(),
        "chunk_plan": chunk_plan_summary(chunk_plan),
    }
    meta_path = write_meta(out_dir, meta_payload)

    result = IngestResult(
        document_id=document_id,
        source=source,
        source_format=source_format,
        raw_filename=raw_path.name,
        raw_bytes=raw_path.stat().st_size,
        markdown_chars=chars,
        markdown_lines=lines,
        output_dir=str(out_dir),
        raw_path=str(raw_path),
        markdown_path=str(md_path),
        meta_path=str(meta_path),
        report_html_path=str(out_dir / "report.html"),
        sections_path=str(sections_path),
        chunks_path=str(chunks_path),
        filing=filing,
        session_id=session_id,
        narrative_checks=meta_payload["narrative_checks"],
        section_outline=outline,
        chunk_plan=chunk_plan,
    )
    report_path = Path(result.report_html_path)
    report_path.write_text(
        build_report_html(result, markdown, outline), encoding="utf-8"
    )

    if not defer_vector_ingest:
        ingest_kw = {}
        if progress is not None:
            ingest_kw["progress"] = progress
            ingest_kw["progress_label"] = label
        try:
            vector_store.ingest(result, **ingest_kw)
        except TypeError:
            vector_store.ingest(result)
            if progress:
                progress.report(f"{label}: chunks uploaded", advance_steps=1)
                progress.report(f"{label}: embedding done", advance_steps=1)
    return result


async def _ingest_vector_async(
    store: VectorStore,
    result: IngestResult,
    *,
    progress: RagIngestProgress | None = None,
    progress_label: str = "",
) -> None:
    ingest_async = getattr(store, "ingest_async", None)
    if ingest_async is not None:
        try:
            await ingest_async(
                result, progress=progress, progress_label=progress_label
            )
            return
        except TypeError:
            await ingest_async(result)
            if progress:
                progress.report(
                    f"{progress_label}: chunks uploaded", advance_steps=1
                )
                progress.report(
                    f"{progress_label}: embedding done", advance_steps=1
                )
            return
    await asyncio.to_thread(store.ingest, result)
    if progress:
        progress.report(f"{progress_label}: chunks uploaded", advance_steps=1)
        progress.report(f"{progress_label}: embedding done", advance_steps=1)


def ingest_from_sec(
    *,
    ticker: str,
    session_id: str | None = None,
    homework_output: bool = False,
    fiscal_year: int | None = None,
    vector_store: VectorStore | None = None,
    progress: RagIngestProgress | None = None,
) -> IngestResult:
    from session_process_store import filing_progress_label

    store = vector_store or get_vector_store()
    document_id, out_dir = allocate_output_dir(
        session_id=session_id,
        ticker=ticker,
        homework_output=homework_output or session_id is None,
    )
    label = filing_progress_label(ticker, fiscal_year)
    if progress:
        progress.report(f"{label}: fetching 10-K from SEC")
    fetched = fetch_latest_annual_report(
        ticker=ticker, out_dir=out_dir, fiscal_year=fiscal_year
    )
    fkey = filing_key_from_meta(fetched.filing_meta)
    label = filing_progress_label(ticker, fkey.year)
    if progress:
        progress.report(f"{label}: SEC fetch done", advance_steps=1)
    return _finalize_ingest(
        document_id=document_id,
        out_dir=out_dir,
        raw_path=fetched.raw_path,
        source=DocumentSource.SEC_ANNUAL,
        source_format=fetched.source_format,
        filing=fetched.filing_meta,
        filing_key=fkey,
        session_id=session_id,
        vector_store=store,
        progress=progress,
        progress_label=label,
    )


async def ingest_from_sec_async(
    *,
    ticker: str,
    session_id: str | None = None,
    homework_output: bool = False,
    fiscal_year: int | None = None,
    vector_store: VectorStore | None = None,
    progress: RagIngestProgress | None = None,
) -> IngestResult:
    from session_process_store import filing_progress_label

    store = vector_store or get_vector_store()
    document_id, out_dir = allocate_output_dir(
        session_id=session_id,
        ticker=ticker,
        homework_output=homework_output or session_id is None,
    )
    label = filing_progress_label(ticker, fiscal_year)
    if progress:
        progress.report(f"{label}: fetching 10-K from SEC")
    async with SEC_FETCH_SEMAPHORE:
        fetched = await asyncio.to_thread(
            fetch_latest_annual_report,
            ticker=ticker,
            out_dir=out_dir,
            fiscal_year=fiscal_year,
        )
    label = filing_progress_label(
        ticker, filing_key_from_meta(fetched.filing_meta).year
    )
    if progress:
        progress.report(f"{label}: SEC fetch done", advance_steps=1)
    fkey = filing_key_from_meta(fetched.filing_meta)
    result = _finalize_ingest(
        document_id=document_id,
        out_dir=out_dir,
        raw_path=fetched.raw_path,
        source=DocumentSource.SEC_ANNUAL,
        source_format=fetched.source_format,
        filing=fetched.filing_meta,
        filing_key=fkey,
        session_id=session_id,
        vector_store=store,
        defer_vector_ingest=True,
        progress=progress,
        progress_label=label,
    )
    await _ingest_vector_async(
        store, result, progress=progress, progress_label=label
    )
    return result


def ingest_from_upload(
    *,
    upload_path: Path,
    original_filename: str,
    ticker: str,
    year: int,
    doctype: str,
    session_id: str | None = None,
    homework_output: bool = False,
    vector_store: VectorStore | None = None,
    progress: RagIngestProgress | None = None,
) -> IngestResult:
    from session_process_store import filing_progress_label

    store = vector_store or get_vector_store()
    filing_key = DocumentFilingKey(ticker=ticker, year=year, doctype=doctype)
    document_id, out_dir = allocate_output_dir(
        session_id=session_id,
        homework_output=homework_output or session_id is None,
    )
    label = filing_progress_label(ticker, year)
    if progress:
        progress.report(f"{label}: reading upload")
    safe_name = Path(original_filename).name or "upload.bin"
    raw_path = out_dir / f"raw_{safe_name}"
    shutil.copy2(upload_path, raw_path)
    if progress:
        progress.report(f"{label}: upload ready", advance_steps=1)
    return _finalize_ingest(
        document_id=document_id,
        out_dir=out_dir,
        raw_path=raw_path,
        source=DocumentSource.MANUAL_UPLOAD,
        source_format=_ext_to_format(raw_path),
        filing=None,
        filing_key=filing_key,
        session_id=session_id,
        vector_store=store,
        progress=progress,
        progress_label=label,
    )
