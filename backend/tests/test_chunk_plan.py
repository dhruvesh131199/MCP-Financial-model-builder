"""Unit tests for parent/sub-chunk splitting (no network)."""

from __future__ import annotations

import math
import uuid

import pytest

from helper.rag.chunk_ids import (
    DocumentFilingKey,
    filing_key_from_meta,
    filing_year,
    normalize_doctype,
    parent_chunk_id,
)
from helper.rag.chunk_plan import (
    PARENT_MAX_CHARS,
    PARENT_OVERLAP,
    PARENT_SPLIT_DIVISOR,
    SUBCHUNK_OVERLAP,
    SUBCHUNK_SIZE,
    build_chunk_plan,
    parent_chunks_for_item,
    split_into_n_with_overlap,
    split_with_overlap,
)
from helper.rag.schema import FilingMeta, ItemSection, SectionOutline
from helper.rag.section_analyze import analyze_sections

ITEMS_FIXTURE = (
    __import__("pathlib").Path(__file__).resolve().parent.parent
    / "helper"
    / "rag"
    / "tests"
    / "fixtures"
    / "sample_10k_items.md"
)

FILING_KEY = DocumentFilingKey(ticker="TEST", year=2025, doctype="10K")


def _repeat_char(c: str, n: int) -> str:
    return c * n


def test_normalize_doctype():
    assert normalize_doctype("10-K") == "10K"
    assert normalize_doctype("10k") == "10K"


def test_filing_year_prefers_period_of_report():
    assert filing_year("2025-09-27", "2025-10-31") == 2025
    assert filing_year(None, "2024-01-15") == 2024


def test_parent_chunk_id_format():
    assert parent_chunk_id("aapl", 2025, "10-K", 1) == "AAPL_2025_10K_P_01"
    assert parent_chunk_id("AAPL", 2025, "10K", 12) == "AAPL_2025_10K_P_12"


def test_filing_key_from_meta():
    meta = FilingMeta(
        ticker="MSFT",
        form="10-K",
        period_of_report="2024-06-30",
        filing_date="2024-07-30",
    )
    key = filing_key_from_meta(meta)
    assert key.ticker == "MSFT"
    assert key.year == 2024
    assert key.doctype == "10K"


def test_parent_no_split_when_under_max():
    text = _repeat_char("a", 10_000)
    parents, next_idx = parent_chunks_for_item(
        text,
        filing_key=FILING_KEY,
        next_chunk_index=1,
    )
    assert len(parents) == 1
    assert parents[0].id == "TEST_2025_10K_P_01"
    assert parents[0].chunk_index == 1
    assert parents[0].char_count == 10_000
    assert next_idx == 2


def test_parent_split_count_22000():
    text = _repeat_char("b", 22_000)
    parents, next_idx = parent_chunks_for_item(
        text,
        filing_key=FILING_KEY,
        next_chunk_index=1,
    )
    assert len(parents) == math.ceil(22_000 / PARENT_SPLIT_DIVISOR)
    assert len(parents) == 3
    assert parents[0].id == "TEST_2025_10K_P_01"
    assert parents[1].id == "TEST_2025_10K_P_02"
    assert parents[2].id == "TEST_2025_10K_P_03"
    assert next_idx == 4


def test_parent_overlap_500():
    text = _repeat_char("c", 22_000)
    parents, _ = parent_chunks_for_item(
        text,
        filing_key=FILING_KEY,
        next_chunk_index=1,
    )
    for i in range(1, len(parents)):
        prev = parents[i - 1]
        curr = parents[i]
        assert prev.content[-PARENT_OVERLAP:] == curr.content[:PARENT_OVERLAP]


def test_parent_piece_max_chars():
    text = _repeat_char("d", 50_000)
    parents, _ = parent_chunks_for_item(
        text,
        filing_key=FILING_KEY,
        next_chunk_index=1,
    )
    for p in parents:
        assert p.char_count <= PARENT_MAX_CHARS


def test_subchunk_size_and_overlap():
    text = _repeat_char("e", 5_000)
    parents, _ = parent_chunks_for_item(
        text,
        filing_key=FILING_KEY,
        next_chunk_index=1,
    )
    subs = parents[0].subchunks
    assert len(subs) > 1
    for s in subs:
        assert len(s.content) <= SUBCHUNK_SIZE
        assert s.embedding is None
        uuid.UUID(s.id)
        assert s.parent_id == parents[0].id
    for i in range(1, len(subs)):
        assert subs[i - 1].content[-SUBCHUNK_OVERLAP:] == subs[i].content[:SUBCHUNK_OVERLAP]


def test_split_with_overlap_windows():
    text = _repeat_char("x", 2500)
    windows = split_with_overlap(text, chunk_size=1000, overlap=200)
    assert windows[0] == (0, 1000)
    assert windows[1][0] == 800
    assert windows[-1][1] == 2500


def test_preamble_skipped_in_build_chunk_plan():
    markdown = "preamble junk\n\n" + "Item 1. Business\n" + _repeat_char("z", 500)
    outline = analyze_sections(markdown)
    plan = build_chunk_plan(markdown, outline, "doc-p", FILING_KEY)
    assert plan.ticker == "TEST"
    assert all(p.id.startswith("TEST_2025_10K_P_") for p in plan.parent_chunks)


def test_global_chunk_index_across_items():
    item1 = _repeat_char("a", 22_000)
    item1a = _repeat_char("b", 1_000)
    markdown = f"Item 1. Business\n{item1}\nItem 1A. Risk\n{item1a}"
    outline = analyze_sections(markdown)
    plan = build_chunk_plan(markdown, outline, "doc-global", FILING_KEY)
    indices = [p.chunk_index for p in plan.parent_chunks]
    assert indices == list(range(1, len(indices) + 1))
    assert plan.parent_chunks[0].id == "TEST_2025_10K_P_01"
    # Item 1 splits into 3 parents; Item 1A is next index 4
    assert plan.parent_chunks[3].id == "TEST_2025_10K_P_04"


def test_parent_chunks_carry_item_label():
    text = _repeat_char("a", 500)
    parents, _ = parent_chunks_for_item(
        text,
        filing_key=FILING_KEY,
        next_chunk_index=1,
        item_id="1A",
        item_label="Item 1A — Risk Factors",
    )
    assert parents[0].item_id == "1A"
    assert parents[0].item_label == "Item 1A — Risk Factors"


def test_subchunk_metadata():
    text = _repeat_char("f", 3_000)
    parents, _ = parent_chunks_for_item(
        text,
        filing_key=FILING_KEY,
        next_chunk_index=5,
    )
    sub = parents[0].subchunks[0]
    assert sub.parent_id == parents[0].id
    assert parents[0].id == "TEST_2025_10K_P_05"
    assert sub.embedding is None


def test_build_chunk_plan_from_fixture():
    text = ITEMS_FIXTURE.read_text(encoding="utf-8")
    outline = analyze_sections(text)
    plan = build_chunk_plan(text, outline, "doc-fix", FILING_KEY)
    assert plan.parent_count == len(plan.parent_chunks)
    assert plan.subchunk_count > 0
    assert plan.subchunk_count == sum(len(p.subchunks) for p in plan.parent_chunks)
    assert outline.items_found >= 1
    assert plan.parent_count >= outline.items_found
    assert all(p.item_label for p in plan.parent_chunks)


def test_split_into_n_covers_full_text():
    text = _repeat_char("g", 22_000)
    windows = split_into_n_with_overlap(
        text,
        num_chunks=3,
        overlap=PARENT_OVERLAP,
        max_chunk_size=PARENT_MAX_CHARS,
    )
    assert windows[0][0] == 0
    assert windows[-1][1] == 22_000
    assert len(windows) == 3
