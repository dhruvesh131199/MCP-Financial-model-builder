"""Parse MarkItDown 10-K output into Item sections with char/token stats."""

from __future__ import annotations

import re
from dataclasses import dataclass

from helper.rag.schema import ItemSection, SectionOutline

ITEM_LINE_RE = re.compile(
    r"^\s*(?:#+\s*)?(?:PART\s+[IVXLC]+\s*[-–—]?\s*)?"
    r"(Item\s+(\d+[A-Z]?))\.?\s*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)


def approx_tokens(char_count: int) -> int:
    return round(char_count / 4)


@dataclass
class _ItemMatch:
    item_id: str
    title: str
    label: str
    start: int


def _clean_title(title: str) -> str:
    t = title.strip().strip(".")
    return re.sub(r"\s+", " ", t)


def _find_item_matches(text: str) -> list[_ItemMatch]:
    matches: list[_ItemMatch] = []
    for m in ITEM_LINE_RE.finditer(text):
        item_id = m.group(2).upper()
        title = _clean_title(m.group(3) or "")
        label = f"Item {item_id}" + (f" — {title}" if title else "")
        matches.append(
            _ItemMatch(
                item_id=item_id,
                title=title,
                label=label,
                start=m.start(),
            )
        )
    return matches


def _dedupe_items_by_largest_span(
    text: str, matches: list[_ItemMatch]
) -> list[_ItemMatch]:
    """Keep one match per item_id — the one with the largest following span (body vs TOC)."""
    if not matches:
        return []

    sorted_by_pos = sorted(matches, key=lambda x: x.start)
    spans: list[tuple[_ItemMatch, int]] = []
    for i, match in enumerate(sorted_by_pos):
        end = sorted_by_pos[i + 1].start if i + 1 < len(sorted_by_pos) else len(text)
        spans.append((match, end - match.start))

    best: dict[str, tuple[_ItemMatch, int]] = {}
    for match, span_len in spans:
        prev = best.get(match.item_id)
        if prev is None or span_len > prev[1]:
            best[match.item_id] = (match, span_len)

    return sorted((m for m, _ in best.values()), key=lambda x: x.start)


def _build_item_section(match: _ItemMatch, end: int) -> ItemSection:
    char_count = end - match.start
    return ItemSection(
        item_id=match.item_id,
        title=match.title,
        label=match.label,
        char_count=char_count,
        approx_tokens=approx_tokens(char_count),
        start_offset=match.start,
    )


def analyze_sections(markdown: str) -> SectionOutline:
    total = len(markdown)
    warnings: list[str] = []
    raw_matches = _find_item_matches(markdown)

    if not raw_matches:
        warnings.append("no Item headers found — showing full document as one row")
        full = ItemSection(
            item_id="full",
            title="Full document",
            label="Full document",
            char_count=total,
            approx_tokens=approx_tokens(total),
            start_offset=0,
        )
        return SectionOutline(
            items=[full],
            preamble=None,
            total_chars=total,
            items_found=0,
            warnings=warnings,
        )

    kept = _dedupe_items_by_largest_span(markdown, raw_matches)
    if len(raw_matches) > len(kept):
        warnings.append(
            f"deduped {len(raw_matches) - len(kept)} duplicate Item header(s) (likely TOC)"
        )

    first_start = kept[0].start
    preamble: ItemSection | None = None
    if first_start > 0:
        preamble = ItemSection(
            item_id="preamble",
            title="XBRL / cover",
            label="Preamble (XBRL / cover)",
            char_count=first_start,
            approx_tokens=approx_tokens(first_start),
            start_offset=0,
        )

    items: list[ItemSection] = []
    for i, match in enumerate(kept):
        end = kept[i + 1].start if i + 1 < len(kept) else total
        items.append(_build_item_section(match, end))

    return SectionOutline(
        items=items,
        preamble=preamble,
        total_chars=total,
        items_found=len(items),
        warnings=warnings,
    )
