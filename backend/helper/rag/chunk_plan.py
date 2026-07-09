"""Parent + sub-chunk splitting for RAG homework."""

from __future__ import annotations

import math
import uuid

from helper.rag.chunk_ids import DocumentFilingKey, parent_chunk_id
from helper.rag.schema import ChunkPlan, ParentChunk, SectionOutline, SubChunk
from helper.rag.section_analyze import approx_tokens

PARENT_MAX_CHARS = 12_000
PARENT_SPLIT_DIVISOR = 10_000
PARENT_OVERLAP = 500
SUBCHUNK_SIZE = 1_000
SUBCHUNK_OVERLAP = 200


def chunk_config() -> dict[str, int]:
    return {
        "parent_max_chars": PARENT_MAX_CHARS,
        "parent_split_divisor": PARENT_SPLIT_DIVISOR,
        "parent_overlap": PARENT_OVERLAP,
        "subchunk_size": SUBCHUNK_SIZE,
        "subchunk_overlap": SUBCHUNK_OVERLAP,
    }


def split_with_overlap(
    text: str, *, chunk_size: int, overlap: int
) -> list[tuple[int, int]]:
    """Sliding windows: fixed chunk_size with overlap between consecutive windows."""
    if not text:
        return []
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")
    n = len(text)
    windows: list[tuple[int, int]] = []
    start = 0
    while start < n:
        end = min(start + chunk_size, n)
        windows.append((start, end))
        if end >= n:
            break
        start = end - overlap
    return windows


def split_into_n_with_overlap(
    text: str,
    *,
    num_chunks: int,
    overlap: int,
    max_chunk_size: int,
) -> list[tuple[int, int]]:
    """Split text into exactly num_chunks windows with overlap between neighbors."""
    n = len(text)
    if num_chunks <= 1 or n == 0:
        return [(0, n)] if n else []

    chunk_size = min(
        max_chunk_size,
        math.ceil((n + (num_chunks - 1) * overlap) / num_chunks),
    )
    windows: list[tuple[int, int]] = []
    start = 0
    for i in range(num_chunks):
        if i == num_chunks - 1:
            end = n
        else:
            end = min(start + chunk_size, n)
        windows.append((start, end))
        if i < num_chunks - 1:
            start = end - overlap
    return windows


def _parent_windows(item_text: str) -> list[tuple[int, int]]:
    n = len(item_text)
    if n <= PARENT_MAX_CHARS:
        return [(0, n)]
    num = math.ceil(n / PARENT_SPLIT_DIVISOR)
    return split_into_n_with_overlap(
        item_text,
        num_chunks=num,
        overlap=PARENT_OVERLAP,
        max_chunk_size=PARENT_MAX_CHARS,
    )


def subchunks_for_parent(parent_text: str, *, parent_id: str) -> list[SubChunk]:
    windows = split_with_overlap(
        parent_text,
        chunk_size=SUBCHUNK_SIZE,
        overlap=SUBCHUNK_OVERLAP,
    )
    subchunks: list[SubChunk] = []
    for rel_start, rel_end in windows:
        body = parent_text[rel_start:rel_end]
        subchunks.append(
            SubChunk(
                id=str(uuid.uuid4()),
                parent_id=parent_id,
                content=body,
                embedding=None,
            )
        )
    return subchunks


def parent_chunks_for_item(
    item_text: str,
    *,
    filing_key: DocumentFilingKey,
    next_chunk_index: int,
    item_id: str | None = None,
    item_label: str | None = None,
) -> tuple[list[ParentChunk], int]:
    windows = _parent_windows(item_text)
    parents: list[ParentChunk] = []
    index = next_chunk_index

    for rel_start, rel_end in windows:
        body = item_text[rel_start:rel_end]
        chunk_id = parent_chunk_id(
            filing_key.ticker,
            filing_key.year,
            filing_key.doctype,
            index,
        )
        parent = ParentChunk(
            id=chunk_id,
            ticker=filing_key.ticker,
            year=filing_key.year,
            doctype=filing_key.doctype,
            chunk_index=index,
            item_id=item_id,
            item_label=item_label,
            content=body,
            char_count=len(body),
            approx_tokens=approx_tokens(len(body)),
            subchunks=[],
        )
        parent.subchunks = subchunks_for_parent(body, parent_id=parent.id)
        parents.append(parent)
        index += 1

    return parents, index


def build_chunk_plan(
    markdown: str,
    outline: SectionOutline,
    document_id: str,
    filing_key: DocumentFilingKey,
) -> ChunkPlan:
    warnings: list[str] = []
    parent_chunks: list[ParentChunk] = []
    next_index = 1

    items = outline.items
    for i, item in enumerate(items):
        if item.item_id == "preamble":
            continue
        end = items[i + 1].start_offset if i + 1 < len(items) else len(markdown)
        item_text = markdown[item.start_offset : end]
        if not item_text.strip():
            warnings.append(f"empty body for {item.label}")
            continue
        new_parents, next_index = parent_chunks_for_item(
            item_text,
            filing_key=filing_key,
            next_chunk_index=next_index,
            item_id=item.item_id,
            item_label=item.label,
        )
        parent_chunks.extend(new_parents)

    if outline.items_found == 0:
        warnings.append(
            "no SEC Item headers detected — chunked as full document (not per-Item)"
        )

    subchunk_count = sum(len(p.subchunks) for p in parent_chunks)
    return ChunkPlan(
        document_id=document_id,
        ticker=filing_key.ticker,
        year=filing_key.year,
        doctype=filing_key.doctype,
        config=chunk_config(),
        parent_chunks=parent_chunks,
        parent_count=len(parent_chunks),
        subchunk_count=subchunk_count,
        warnings=warnings,
    )


def chunk_plan_summary(plan: ChunkPlan) -> dict:
    """Lightweight summary for meta.json (no chunk text)."""
    return {
        "document_id": plan.document_id,
        "ticker": plan.ticker,
        "year": plan.year,
        "doctype": plan.doctype,
        "config": plan.config,
        "parent_count": plan.parent_count,
        "subchunk_count": plan.subchunk_count,
        "warnings": plan.warnings,
    }
