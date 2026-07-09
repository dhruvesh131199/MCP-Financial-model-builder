"""Load chunk plans from on-disk ingest folders."""

from __future__ import annotations

import json
from pathlib import Path

from helper.rag.chunk_ids import DocumentFilingKey, filing_key_from_meta
from helper.rag.chunk_plan import build_chunk_plan
from helper.rag.schema import FilingMeta, SectionOutline


def filing_key_from_meta_dict(meta: dict) -> DocumentFilingKey:
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


def load_section_outline(out_dir: Path, meta: dict) -> dict | None:
    if meta.get("section_outline"):
        return meta["section_outline"]
    sections_path = out_dir / "sections.json"
    if sections_path.is_file():
        return json.loads(sections_path.read_text(encoding="utf-8"))
    return None


def load_chunk_plan(out_dir: Path, meta: dict) -> dict | None:
    chunks_path = out_dir / "chunks.json"
    if chunks_path.is_file():
        return json.loads(chunks_path.read_text(encoding="utf-8"))
    outline_data = load_section_outline(out_dir, meta)
    md_path = out_dir / "converted.md"
    if not outline_data or not md_path.is_file():
        return None
    markdown = md_path.read_text(encoding="utf-8", errors="replace")
    outline = SectionOutline.model_validate(outline_data)
    try:
        filing_key = filing_key_from_meta_dict(meta)
    except ValueError:
        return None
    plan = build_chunk_plan(
        markdown, outline, meta.get("document_id", ""), filing_key
    )
    return plan.model_dump()
