"""Tests for resolve_or_ingest dedup and session index linking."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import store as store_module
from homework.rag_markitdown.postgres_read import FilingLookup, lookup_filing
from homework.rag_markitdown.resolve import resolve_or_ingest_sec, resolve_or_ingest_upload
from homework.rag_markitdown.schema import (
    ChunkPlan,
    DocumentSource,
    FilingMeta,
    IngestResult,
    ParentChunk,
    SourceFormat,
    SubChunk,
)
from rag_session_store import list_rag_documents
from store import create_session, load_workspace


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)


def _mock_filing_meta() -> FilingMeta:
    return FilingMeta(
        ticker="AAPL",
        form="10-K",
        period_of_report="2025-09-27",
        filing_date="2025-10-31",
    )


def _mock_ingest_result(doc_id: str = "doc-new") -> IngestResult:
    parent = ParentChunk(
        id="AAPL_2025_10K_P_01",
        ticker="AAPL",
        year=2025,
        doctype="10K",
        chunk_index=1,
        content="parent",
        char_count=6,
        approx_tokens=2,
        subchunks=[
            SubChunk(id="sub-1", parent_id="AAPL_2025_10K_P_01", content="sub", embedding=None),
        ],
    )
    plan = ChunkPlan(
        document_id=doc_id,
        ticker="AAPL",
        year=2025,
        doctype="10K",
        parent_chunks=[parent],
        parent_count=1,
        subchunk_count=1,
    )
    return IngestResult(
        document_id=doc_id,
        source=DocumentSource.SEC_ANNUAL,
        source_format=SourceFormat.HTML,
        raw_filename="raw.html",
        raw_bytes=100,
        markdown_chars=100,
        markdown_lines=5,
        output_dir="/tmp",
        raw_path="/tmp/raw.html",
        markdown_path="/tmp/converted.md",
        meta_path="/tmp/meta.json",
        report_html_path="/tmp/report.html",
        chunk_plan=plan,
    )


def test_lookup_filing_miss_without_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert lookup_filing("AAPL", 2025, "10K") is None


@pytest.mark.skipif(
    not __import__("os").getenv("DATABASE_URL"),
    reason="DATABASE_URL not set",
)
def test_lookup_filing_hit_after_ingest():
    import uuid

    from homework.rag_markitdown.postgres_store import PostgresVectorStore
    from homework.rag_markitdown.schema import (
        ChunkPlan,
        DocumentSource,
        IngestResult,
        ParentChunk,
        SourceFormat,
        SubChunk,
    )

    parent = ParentChunk(
        id="TEST_2099_10K_P_01",
        ticker="TEST",
        year=2099,
        doctype="10K",
        chunk_index=1,
        content="parent body",
        char_count=11,
        approx_tokens=3,
        subchunks=[
            SubChunk(
                id=str(uuid.uuid4()),
                parent_id="TEST_2099_10K_P_01",
                content="sub one",
                embedding=None,
            ),
        ],
    )
    plan = ChunkPlan(
        document_id=str(uuid.uuid4()),
        ticker="TEST",
        year=2099,
        doctype="10K",
        parent_chunks=[parent],
        parent_count=1,
        subchunk_count=1,
    )
    result = IngestResult(
        document_id=plan.document_id,
        source=DocumentSource.MANUAL_UPLOAD,
        source_format=SourceFormat.HTML,
        raw_filename="raw_test.html",
        raw_bytes=100,
        markdown_chars=100,
        markdown_lines=5,
        output_dir="/tmp",
        raw_path="/tmp/raw_test.html",
        markdown_path="/tmp/converted.md",
        meta_path="/tmp/meta.json",
        report_html_path="/tmp/report.html",
        chunk_plan=plan,
    )

    store = PostgresVectorStore()
    store.ingest(result)
    try:
        hit = lookup_filing("TEST", 2099, "10K")
        assert hit is not None
        assert hit.document_id == result.document_id
        assert hit.parent_count == 1
        assert hit.subchunk_count == 1
    finally:
        import psycopg
        from homework.rag_markitdown.db import get_database_url

        url = get_database_url()
        assert url
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM parent_chunks WHERE ticker = %s AND year = %s",
                    ("TEST", 2099),
                )
                cur.execute(
                    "DELETE FROM documents WHERE ticker = %s AND year = %s",
                    ("TEST", 2099),
                )
            conn.commit()


@patch("homework.rag_markitdown.resolve.ingest_from_sec")
@patch("homework.rag_markitdown.resolve.lookup_filing")
@patch("homework.rag_markitdown.resolve.get_database_url", return_value="postgresql://x")
@patch("homework.rag_markitdown.resolve.peek_latest_annual_filing_meta")
@patch("homework.rag_markitdown.resolve.count_unembedded", return_value=0)
@patch("homework.rag_markitdown.resolve.embed_document")
def test_sec_resolve_skips_ingest_on_cache_hit(
    mock_embed, mock_count, mock_peek, _mock_db_url, mock_lookup, mock_ingest
):
    sid = create_session()
    mock_peek.return_value = _mock_filing_meta()
    mock_lookup.return_value = FilingLookup(
        document_id="cached-doc",
        ticker="AAPL",
        year=2025,
        doctype="10K",
        source="sec_annual",
        parent_count=3,
        subchunk_count=12,
        created_at="2026-01-01",
    )

    result = resolve_or_ingest_sec(session_id=sid, ticker="AAPL")

    assert result.success is True
    assert result.from_cache is True
    assert result.document_id == "cached-doc"
    mock_ingest.assert_not_called()
    mock_embed.assert_not_called()

    docs = list_rag_documents(sid)
    assert len(docs) == 1
    assert docs[0]["filing_key"] == "AAPL_2025_10K"
    assert docs[0]["from_cache"] is True
    ws = load_workspace(sid)
    assert ws is not None
    assert len(ws["rag_documents"]) == 1


@patch("homework.rag_markitdown.resolve.ingest_from_sec")
@patch("homework.rag_markitdown.resolve.lookup_filing")
@patch("homework.rag_markitdown.resolve.get_database_url", return_value="postgresql://x")
@patch("homework.rag_markitdown.resolve.peek_latest_annual_filing_meta")
@patch("homework.rag_markitdown.resolve.count_unembedded", return_value=5)
@patch("homework.rag_markitdown.resolve.embed_document")
def test_sec_resolve_backfills_embed_on_cache_hit(
    mock_embed, mock_count, mock_peek, _mock_db_url, mock_lookup, mock_ingest
):
    sid = create_session()
    mock_peek.return_value = _mock_filing_meta()
    mock_lookup.return_value = FilingLookup(
        document_id="cached-doc",
        ticker="AAPL",
        year=2025,
        doctype="10K",
        source="sec_annual",
        parent_count=3,
        subchunk_count=12,
        created_at="2026-01-01",
    )

    result = resolve_or_ingest_sec(session_id=sid, ticker="AAPL")

    assert result.from_cache is True
    mock_ingest.assert_not_called()
    mock_embed.assert_called_once_with("cached-doc")


@patch("homework.rag_markitdown.resolve.ingest_from_sec")
@patch("homework.rag_markitdown.resolve.lookup_filing", return_value=None)
@patch("homework.rag_markitdown.resolve.get_database_url", return_value="postgresql://x")
@patch("homework.rag_markitdown.resolve.peek_latest_annual_filing_meta")
def test_sec_resolve_full_ingest_on_miss(
    mock_peek, _mock_db_url, _mock_lookup, mock_ingest
):
    sid = create_session()
    mock_peek.return_value = _mock_filing_meta()
    mock_ingest.return_value = _mock_ingest_result("doc-fresh")

    result = resolve_or_ingest_sec(session_id=sid, ticker="AAPL")

    assert result.success is True
    assert result.from_cache is False
    assert result.document_id == "doc-fresh"
    mock_ingest.assert_called_once()

    docs = list_rag_documents(sid)
    assert docs[0]["status"] == "ready"
    assert docs[0]["from_cache"] is False


@patch("homework.rag_markitdown.resolve.ingest_from_upload")
@patch("homework.rag_markitdown.resolve.lookup_filing")
@patch("homework.rag_markitdown.resolve.get_database_url", return_value="postgresql://x")
@patch("homework.rag_markitdown.resolve.count_unembedded", return_value=0)
@patch("homework.rag_markitdown.resolve.embed_document")
def test_upload_resolve_dedup(mock_embed, mock_count, mock_db_url, mock_lookup, mock_ingest, tmp_path):
    sid = create_session()
    upload = tmp_path / "filing.html"
    upload.write_text("<html>test</html>", encoding="utf-8")
    mock_lookup.return_value = FilingLookup(
        document_id="upload-cached",
        ticker="MSFT",
        year=2024,
        doctype="10K",
        source="manual_upload",
        parent_count=2,
        subchunk_count=5,
        created_at=None,
    )

    result = resolve_or_ingest_upload(
        session_id=sid,
        upload_path=upload,
        original_filename="filing.html",
        ticker="MSFT",
        year=2024,
        doctype="10K",
    )

    assert result.from_cache is True
    assert result.document_id == "upload-cached"
    mock_ingest.assert_not_called()
    assert list_rag_documents(sid)[0]["filing_key"] == "MSFT_2024_10K"
