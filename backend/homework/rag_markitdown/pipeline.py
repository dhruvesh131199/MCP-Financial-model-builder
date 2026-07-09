"""Single entry: raw file → MarkItDown → saved artifacts."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

from homework.rag_markitdown.chunk_ids import DocumentFilingKey, filing_key_from_meta
from homework.rag_markitdown.chunk_plan import build_chunk_plan, chunk_plan_summary
from homework.rag_markitdown.convert import convert_file_to_markdown, markdown_stats
from homework.rag_markitdown.fetch_annual import fetch_latest_annual_report
from homework.rag_markitdown.report_html import build_report_html
from homework.rag_markitdown.section_analyze import analyze_sections
from homework.rag_markitdown.schema import (
    DocumentSource,
    FilingMeta,
    IngestResult,
    SourceFormat,
)
from homework.rag_markitdown.storage import allocate_output_dir, write_meta
from homework.rag_markitdown.vector_store import VectorStore, get_vector_store

NARRATIVE_MARKERS = (
    ("risk_factors", "risk factors"),
    ("md_and_a", "management"),
    ("financial_statements", "financial statements"),
)


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


def _emit_step(on_step: Callable[[str], None] | None, message: str) -> None:
    if on_step:
        on_step(message)


def _filing_progress_label(filing_key: DocumentFilingKey) -> str:
    return f"{filing_key.ticker} FY{filing_key.year}"


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
    on_step: Callable[[str], None] | None = None,
) -> IngestResult:
    label = _filing_progress_label(filing_key)
    _emit_step(on_step, f"Converting {label} to Markdown")
    markdown = convert_file_to_markdown(raw_path)
    md_path = out_dir / "converted.md"
    md_path.write_text(markdown, encoding="utf-8")
    chars, lines = markdown_stats(markdown)
    _emit_step(on_step, f"Analyzing {label} sections")
    outline = analyze_sections(markdown)
    sections_path = out_dir / "sections.json"
    sections_path.write_text(
        json.dumps(outline.model_dump(), indent=2), encoding="utf-8"
    )
    chunk_plan = build_chunk_plan(markdown, outline, document_id, filing_key)
    _emit_step(
        on_step,
        f"Created {chunk_plan.parent_count} parent chunks and "
        f"{chunk_plan.subchunk_count} sub-chunks for {label}",
    )
    chunks_path = out_dir / "chunks.json"
    chunks_path.write_text(
        json.dumps(chunk_plan.model_dump(), indent=2), encoding="utf-8"
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

    vector_store.ingest(result, on_step=on_step)
    return result


def ingest_from_sec(
    *,
    ticker: str,
    session_id: str | None = None,
    homework_output: bool = False,
    fiscal_year: int | None = None,
    vector_store: VectorStore | None = None,
    on_step: Callable[[str], None] | None = None,
) -> IngestResult:
    store = vector_store or get_vector_store()
    document_id, out_dir = allocate_output_dir(
        session_id=session_id,
        ticker=ticker,
        homework_output=homework_output or session_id is None,
    )
    sym = ticker.strip().upper()
    year_label = f"FY{fiscal_year}" if fiscal_year else "latest"
    _emit_step(on_step, f"Fetching {sym} {year_label} 10-K from SEC EDGAR")
    fetched = fetch_latest_annual_report(
        ticker=ticker, out_dir=out_dir, fiscal_year=fiscal_year
    )
    filing_key = filing_key_from_meta(fetched.filing_meta)
    return _finalize_ingest(
        document_id=document_id,
        out_dir=out_dir,
        raw_path=fetched.raw_path,
        source=DocumentSource.SEC_ANNUAL,
        source_format=fetched.source_format,
        filing=fetched.filing_meta,
        filing_key=filing_key,
        session_id=session_id,
        vector_store=store,
        on_step=on_step,
    )


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
) -> IngestResult:
    store = vector_store or get_vector_store()
    filing_key = DocumentFilingKey(ticker=ticker, year=year, doctype=doctype)
    document_id, out_dir = allocate_output_dir(
        session_id=session_id,
        homework_output=homework_output or session_id is None,
    )
    safe_name = Path(original_filename).name or "upload.bin"
    raw_path = out_dir / f"raw_{safe_name}"
    shutil.copy2(upload_path, raw_path)
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
    )
