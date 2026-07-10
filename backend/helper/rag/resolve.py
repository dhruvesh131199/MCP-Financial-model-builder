"""Resolve-or-ingest: global Postgres dedup + per-session RAG index."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from helper.rag.chunk_ids import (
    DocumentFilingKey,
    filing_key_from_meta,
    filing_key_string,
    filing_label,
)
from helper.postgres.db import get_database_url
from helper.rag.fetch_annual import peek_latest_annual_filing_meta
from helper.rag.pipeline import ingest_from_sec, ingest_from_sec_async, ingest_from_upload
from helper.postgres.postgres_embed import count_unembedded, embed_document, embed_document_async
from helper.postgres.postgres_read import lookup_filing
from helper.rag.schema import DocumentSource, IngestResult
from helper.rag.vector_store import VectorStore, get_vector_store
from helper.rag.storage import (
    ensure_session_document_dir,
    session_document_has_report,
)
from rag_session_store import (
    rag_document_api_urls,
    record_rag_error,
    upsert_rag_document,
)

logger = logging.getLogger(__name__)


@dataclass
class RagResolveResult:
    success: bool
    from_cache: bool
    status: str
    document_id: str | None
    filing_key: str | None
    rag_entry_id: str | None
    label: str | None
    ticker: str | None
    year: int | None
    doctype: str | None
    source: str | None
    parent_count: int
    subchunk_count: int
    error: str | None = None
    ingest: IngestResult | None = None

    def to_dict(self) -> dict[str, Any]:
        base = {
            "success": self.success,
            "from_cache": self.from_cache,
            "status": self.status,
            "document_id": self.document_id,
            "filing_key": self.filing_key,
            "rag_entry_id": self.rag_entry_id,
            "label": self.label,
            "ticker": self.ticker,
            "year": self.year,
            "doctype": self.doctype,
            "source": self.source,
            "parent_count": self.parent_count,
            "subchunk_count": self.subchunk_count,
            "error": self.error,
        }
        if self.ingest:
            base.update(self.ingest.to_summary_dict())
        return base


def _link_to_session(
    session_id: str,
    *,
    document_id: str,
    filing_key: DocumentFilingKey,
    source: str,
    from_cache: bool,
    parent_count: int,
    subchunk_count: int,
) -> dict[str, Any]:
    if from_cache:
        ensure_session_document_dir(session_id, document_id)
    fkey = filing_key_string(filing_key.ticker, filing_key.year, filing_key.doctype)
    urls = rag_document_api_urls(session_id, document_id)
    has_report = session_document_has_report(session_id, document_id)
    return upsert_rag_document(
        session_id,
        {
            "filing_key": fkey,
            "document_id": document_id,
            "ticker": filing_key.ticker,
            "year": filing_key.year,
            "doctype": filing_key.doctype,
            "label": filing_label(
                filing_key.ticker, filing_key.year, filing_key.doctype
            ),
            "source": source,
            "status": "ready",
            "error": None,
            "from_cache": from_cache,
            "parent_count": parent_count,
            "subchunk_count": subchunk_count,
            **urls,
            "has_report": has_report,
        },
    )


def _after_full_ingest(session_id: str, result: IngestResult) -> dict[str, Any]:
    plan = result.chunk_plan
    assert plan is not None
    return _link_to_session(
        session_id,
        document_id=result.document_id,
        filing_key=DocumentFilingKey(
            ticker=plan.ticker, year=plan.year, doctype=plan.doctype
        ),
        source=result.source.value,
        from_cache=False,
        parent_count=plan.parent_count,
        subchunk_count=plan.subchunk_count,
    )


def resolve_or_ingest_sec(
    *,
    session_id: str,
    ticker: str,
    fiscal_year: int | None = None,
    vector_store: VectorStore | None = None,
) -> RagResolveResult:
    sym = ticker.strip().upper()
    store = vector_store or get_vector_store()
    try:
        filing_meta = peek_latest_annual_filing_meta(ticker=sym, fiscal_year=fiscal_year)
        filing_key = filing_key_from_meta(filing_meta)
        if get_database_url():
            hit = lookup_filing(
                filing_key.ticker, filing_key.year, filing_key.doctype
            )
            if hit:
                if count_unembedded(hit.document_id) > 0:
                    embed_document(hit.document_id)
                entry = _link_to_session(
                    session_id,
                    document_id=hit.document_id,
                    filing_key=filing_key,
                    source=hit.source or DocumentSource.SEC_ANNUAL.value,
                    from_cache=True,
                    parent_count=hit.parent_count,
                    subchunk_count=hit.subchunk_count,
                )
                logger.info(
                    "rag cache hit %s session=%s", entry["filing_key"], session_id
                )
                return RagResolveResult(
                    success=True,
                    from_cache=True,
                    status="ready",
                    document_id=hit.document_id,
                    filing_key=entry["filing_key"],
                    rag_entry_id=entry["id"],
                    label=entry["label"],
                    ticker=filing_key.ticker,
                    year=filing_key.year,
                    doctype=filing_key.doctype,
                    source=entry.get("source"),
                    parent_count=hit.parent_count,
                    subchunk_count=hit.subchunk_count,
                )

        result = ingest_from_sec(
            ticker=sym,
            session_id=session_id,
            homework_output=False,
            fiscal_year=fiscal_year,
            vector_store=store,
        )
        entry = _after_full_ingest(session_id, result)
        plan = result.chunk_plan
        return RagResolveResult(
            success=True,
            from_cache=False,
            status="ready",
            document_id=result.document_id,
            filing_key=entry["filing_key"],
            rag_entry_id=entry["id"],
            label=entry["label"],
            ticker=plan.ticker if plan else filing_key.ticker,
            year=plan.year if plan else filing_key.year,
            doctype=plan.doctype if plan else filing_key.doctype,
            source=result.source.value,
            parent_count=plan.parent_count if plan else 0,
            subchunk_count=plan.subchunk_count if plan else 0,
            ingest=result,
        )
    except Exception as exc:
        logger.exception("rag sec resolve failed ticker=%s", sym)
        entry = record_rag_error(
            session_id,
            label=f"{sym} 10-K",
            ticker=sym,
            error=str(exc),
            source=DocumentSource.SEC_ANNUAL.value,
        )
        return RagResolveResult(
            success=False,
            from_cache=False,
            status="error",
            document_id=None,
            filing_key=entry.get("filing_key"),
            rag_entry_id=entry.get("id"),
            label=entry.get("label"),
            ticker=sym,
            year=None,
            doctype=None,
            source=DocumentSource.SEC_ANNUAL.value,
            parent_count=0,
            subchunk_count=0,
            error=str(exc),
        )


async def resolve_or_ingest_sec_async(
    *,
    session_id: str,
    ticker: str,
    fiscal_year: int | None = None,
    vector_store: VectorStore | None = None,
) -> RagResolveResult:
    sym = ticker.strip().upper()
    store = vector_store or get_vector_store()
    try:
        filing_meta = peek_latest_annual_filing_meta(ticker=sym, fiscal_year=fiscal_year)
        filing_key = filing_key_from_meta(filing_meta)
        if get_database_url():
            hit = lookup_filing(
                filing_key.ticker, filing_key.year, filing_key.doctype
            )
            if hit:
                if count_unembedded(hit.document_id) > 0:
                    await embed_document_async(hit.document_id)
                entry = _link_to_session(
                    session_id,
                    document_id=hit.document_id,
                    filing_key=filing_key,
                    source=hit.source or DocumentSource.SEC_ANNUAL.value,
                    from_cache=True,
                    parent_count=hit.parent_count,
                    subchunk_count=hit.subchunk_count,
                )
                logger.info(
                    "rag cache hit %s session=%s", entry["filing_key"], session_id
                )
                return RagResolveResult(
                    success=True,
                    from_cache=True,
                    status="ready",
                    document_id=hit.document_id,
                    filing_key=entry["filing_key"],
                    rag_entry_id=entry["id"],
                    label=entry["label"],
                    ticker=filing_key.ticker,
                    year=filing_key.year,
                    doctype=filing_key.doctype,
                    source=entry.get("source"),
                    parent_count=hit.parent_count,
                    subchunk_count=hit.subchunk_count,
                )

        result = await ingest_from_sec_async(
            ticker=sym,
            session_id=session_id,
            homework_output=False,
            fiscal_year=fiscal_year,
            vector_store=store,
        )
        entry = _after_full_ingest(session_id, result)
        plan = result.chunk_plan
        return RagResolveResult(
            success=True,
            from_cache=False,
            status="ready",
            document_id=result.document_id,
            filing_key=entry["filing_key"],
            rag_entry_id=entry["id"],
            label=entry["label"],
            ticker=plan.ticker if plan else filing_key.ticker,
            year=plan.year if plan else filing_key.year,
            doctype=plan.doctype if plan else filing_key.doctype,
            source=result.source.value,
            parent_count=plan.parent_count if plan else 0,
            subchunk_count=plan.subchunk_count if plan else 0,
            ingest=result,
        )
    except Exception as exc:
        logger.exception("rag sec resolve failed ticker=%s", sym)
        entry = record_rag_error(
            session_id,
            label=f"{sym} 10-K",
            ticker=sym,
            error=str(exc),
            source=DocumentSource.SEC_ANNUAL.value,
        )
        return RagResolveResult(
            success=False,
            from_cache=False,
            status="error",
            document_id=None,
            filing_key=entry.get("filing_key"),
            rag_entry_id=entry.get("id"),
            label=entry.get("label"),
            ticker=sym,
            year=None,
            doctype=None,
            source=DocumentSource.SEC_ANNUAL.value,
            parent_count=0,
            subchunk_count=0,
            error=str(exc),
        )


def resolve_or_ingest_upload(
    *,
    session_id: str,
    upload_path: Path,
    original_filename: str,
    ticker: str,
    year: int,
    doctype: str,
    vector_store: VectorStore | None = None,
) -> RagResolveResult:
    sym = ticker.strip().upper()
    filing_key = DocumentFilingKey(ticker=sym, year=year, doctype=doctype)
    fkey = filing_key_string(sym, year, filing_key.doctype)
    label = filing_label(sym, year, filing_key.doctype)
    store = vector_store or get_vector_store()
    try:
        if get_database_url():
            hit = lookup_filing(sym, year, filing_key.doctype)
            if hit:
                if count_unembedded(hit.document_id) > 0:
                    embed_document(hit.document_id)
                entry = _link_to_session(
                    session_id,
                    document_id=hit.document_id,
                    filing_key=filing_key,
                    source=hit.source or DocumentSource.MANUAL_UPLOAD.value,
                    from_cache=True,
                    parent_count=hit.parent_count,
                    subchunk_count=hit.subchunk_count,
                )
                return RagResolveResult(
                    success=True,
                    from_cache=True,
                    status="ready",
                    document_id=hit.document_id,
                    filing_key=entry["filing_key"],
                    rag_entry_id=entry["id"],
                    label=entry["label"],
                    ticker=sym,
                    year=year,
                    doctype=filing_key.doctype,
                    source=entry.get("source"),
                    parent_count=hit.parent_count,
                    subchunk_count=hit.subchunk_count,
                )

        result = ingest_from_upload(
            upload_path=upload_path,
            original_filename=original_filename,
            ticker=sym,
            year=year,
            doctype=doctype,
            session_id=session_id,
            homework_output=False,
            vector_store=store,
        )
        entry = _after_full_ingest(session_id, result)
        plan = result.chunk_plan
        return RagResolveResult(
            success=True,
            from_cache=False,
            status="ready",
            document_id=result.document_id,
            filing_key=entry["filing_key"],
            rag_entry_id=entry["id"],
            label=entry["label"],
            ticker=sym,
            year=year,
            doctype=filing_key.doctype,
            source=result.source.value,
            parent_count=plan.parent_count if plan else 0,
            subchunk_count=plan.subchunk_count if plan else 0,
            ingest=result,
        )
    except Exception as exc:
        logger.exception("rag upload resolve failed %s", original_filename)
        entry = record_rag_error(
            session_id,
            label=original_filename,
            ticker=sym,
            year=year,
            doctype=filing_key.doctype,
            error=str(exc),
            source=DocumentSource.MANUAL_UPLOAD.value,
        )
        return RagResolveResult(
            success=False,
            from_cache=False,
            status="error",
            document_id=None,
            filing_key=fkey,
            rag_entry_id=entry.get("id"),
            label=label,
            ticker=sym,
            year=year,
            doctype=filing_key.doctype,
            source=DocumentSource.MANUAL_UPLOAD.value,
            parent_count=0,
            subchunk_count=0,
            error=str(exc),
        )
