"""Fetch primary 10-K (PDF attachment if any, else full HTML)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from edgar import Company

from homework.rag_markitdown.chunk_ids import filing_year
from homework.rag_markitdown.schema import FilingMeta, SourceFormat
from ingest.edgar_identity import ensure_edgar_identity


@dataclass
class FetchedAnnual:
    raw_path: Path
    source_format: SourceFormat
    filing_meta: FilingMeta


def _pick_pdf_attachment(filing: Any) -> Any | None:
    for att in filing.attachments:
        doc = str(getattr(att, "document", "") or "").lower()
        if doc.endswith(".pdf"):
            return att
    return None


def _filing_fiscal_year(filing: Any) -> int | None:
    por = str(getattr(filing, "period_of_report", "") or "")[:10] or None
    fdate = str(getattr(filing, "filing_date", "") or "")[:10] or None
    try:
        return filing_year(por, fdate)
    except ValueError:
        return None


def _resolve_10k_filing(company: Company, fiscal_year: int | None) -> Any:
    filings = company.get_filings(form="10-K", amendments=False)
    if fiscal_year is None:
        filing = filings.latest()
        if filing is None:
            raise ValueError(f"No 10-K found for {company}")
        return filing

    matches: list[Any] = []
    for filing in filings:
        fy = _filing_fiscal_year(filing)
        if fy == fiscal_year:
            matches.append(filing)

    if not matches:
        sym = getattr(company, "ticker", None) or getattr(company, "name", "company")
        raise ValueError(f"No 10-K found for {sym} fiscal year {fiscal_year}")

    # Prefer most recent filing_date when multiple match
    return max(
        matches,
        key=lambda f: str(getattr(f, "filing_date", "") or ""),
    )


def _meta_from_filing(company: Company, filing: Any, sym: str) -> FilingMeta:
    return FilingMeta(
        ticker=sym,
        entity_name=str(getattr(company, "name", sym) or sym),
        cik=str(getattr(company, "cik", "") or ""),
        form=str(getattr(filing, "form", "10-K") or "10-K"),
        accession_no=str(getattr(filing, "accession_no", "") or ""),
        filing_date=str(getattr(filing, "filing_date", ""))[:10] or None,
        period_of_report=str(getattr(filing, "period_of_report", ""))[:10] or None,
        primary_document=str(getattr(filing, "primary_document", "") or "") or None,
    )


def peek_latest_annual_filing_meta(
    *,
    ticker: str,
    fiscal_year: int | None = None,
) -> FilingMeta:
    """SEC metadata only — no download (for Postgres dedup before ingest)."""
    ensure_edgar_identity()
    sym = ticker.strip().upper()
    company = Company(sym)
    filing = _resolve_10k_filing(company, fiscal_year)
    return _meta_from_filing(company, filing, sym)


def fetch_latest_annual_report(
    *,
    ticker: str,
    out_dir: Path,
    fiscal_year: int | None = None,
) -> FetchedAnnual:
    ensure_edgar_identity()
    sym = ticker.strip().upper()
    company = Company(sym)
    filing = _resolve_10k_filing(company, fiscal_year)
    meta = _meta_from_filing(company, filing, sym)

    pdf_att = _pick_pdf_attachment(filing)
    if pdf_att is not None:
        raw_name = Path(str(pdf_att.document)).name or "annual.pdf"
        raw_path = out_dir / f"raw_{raw_name}"
        content = pdf_att.download()
        if isinstance(content, bytes):
            raw_path.write_bytes(content)
        elif isinstance(content, str):
            raw_path.write_text(content, encoding="utf-8")
        else:
            raise ValueError("Could not download PDF attachment")
        return FetchedAnnual(
            raw_path=raw_path,
            source_format=SourceFormat.PDF,
            filing_meta=meta,
        )

    html = filing.html()
    if not html or not str(html).strip():
        raise ValueError(f"Empty 10-K HTML for {sym}")
    primary = meta.primary_document or f"{sym.lower()}-10k.htm"
    raw_path = out_dir / f"raw_{Path(primary).name}"
    raw_path.write_text(str(html), encoding="utf-8")
    return FetchedAnnual(
        raw_path=raw_path,
        source_format=SourceFormat.HTML,
        filing_meta=meta,
    )
