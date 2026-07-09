"""Deterministic parent chunk IDs and filing key for Aurora-ready metadata."""

from __future__ import annotations

from dataclasses import dataclass

from helper.rag.schema import FilingMeta

ALLOWED_DOCTYPES = frozenset({"10K"})


@dataclass(frozen=True)
class DocumentFilingKey:
    ticker: str
    year: int
    doctype: str

    def __post_init__(self) -> None:
        normalized = normalize_doctype(self.doctype)
        object.__setattr__(self, "ticker", self.ticker.strip().upper())
        object.__setattr__(self, "doctype", normalized)
        if self.doctype not in ALLOWED_DOCTYPES:
            raise ValueError(f"Unsupported doctype: {self.doctype!r}")
        if self.year < 1990 or self.year > 2100:
            raise ValueError(f"Invalid filing year: {self.year}")


def normalize_doctype(form: str) -> str:
    """e.g. 10-K → 10K"""
    return form.strip().upper().replace("-", "")


def filing_year(
    period_of_report: str | None,
    filing_date: str | None,
) -> int:
    """Prefer period_of_report year, else filing_date year."""
    for raw in (period_of_report, filing_date):
        if raw and len(raw) >= 4 and raw[:4].isdigit():
            return int(raw[:4])
    raise ValueError("Cannot derive filing year from period_of_report or filing_date")


def parent_chunk_id(
    ticker: str,
    year: int,
    doctype: str,
    chunk_index: int,
) -> str:
    """e.g. AAPL_2025_10K_P_01"""
    norm = normalize_doctype(doctype)
    return f"{ticker.strip().upper()}_{year}_{norm}_P_{chunk_index:02d}"


def filing_key_string(ticker: str, year: int, doctype: str) -> str:
    """e.g. AAPL_2025_10K — stable dedup / display key."""
    norm = normalize_doctype(doctype)
    return f"{ticker.strip().upper()}_{year}_{norm}"


def filing_label(ticker: str, year: int, doctype: str) -> str:
    norm = normalize_doctype(doctype)
    form = "10-K" if norm == "10K" else norm
    return f"{ticker.strip().upper()} · {form} · FY{year}"


def filing_key_from_meta(filing: FilingMeta) -> DocumentFilingKey:
    ticker = (filing.ticker or "").strip().upper()
    if not ticker:
        raise ValueError("Filing meta missing ticker")
    year = filing_year(filing.period_of_report, filing.filing_date)
    doctype = normalize_doctype(filing.form or "10-K")
    return DocumentFilingKey(ticker=ticker, year=year, doctype=doctype)
