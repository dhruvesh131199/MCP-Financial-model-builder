"""Tests for Postgres vector store (optional integration via DATABASE_URL)."""

from __future__ import annotations

import os
import uuid

import pytest

from homework.rag_markitdown.db import get_database_url, schema_is_ready
from homework.rag_markitdown.postgres_store import PostgresVectorStore
from homework.rag_markitdown.schema import (
    ChunkPlan,
    DocumentSource,
    IngestResult,
    ParentChunk,
    SourceFormat,
    SubChunk,
)
from homework.rag_markitdown.vector_store import NoOpVectorStore, get_vector_store


def _sample_result() -> IngestResult:
    parent = ParentChunk(
        id="TEST_2099_10K_P_01",
        ticker="TEST",
        year=2099,
        doctype="10K",
        chunk_index=1,
        content="parent body for postgres test",
        char_count=28,
        approx_tokens=7,
        subchunks=[
            SubChunk(
                id=str(uuid.uuid4()),
                parent_id="TEST_2099_10K_P_01",
                content="sub one",
                embedding=None,
            ),
            SubChunk(
                id=str(uuid.uuid4()),
                parent_id="TEST_2099_10K_P_01",
                content="sub two",
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
        subchunk_count=2,
    )
    return IngestResult(
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


def test_get_vector_store_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    store = get_vector_store()
    assert isinstance(store, NoOpVectorStore)


def test_get_vector_store_with_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    store = get_vector_store()
    assert isinstance(store, PostgresVectorStore)


@pytest.mark.skipif(not get_database_url(), reason="DATABASE_URL not set")
def test_postgres_store_ingest_roundtrip():
    import psycopg

    store = PostgresVectorStore()
    result = _sample_result()
    store.ingest(result)

    url = get_database_url()
    assert url
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM parent_chunks WHERE id = %s",
                ("TEST_2099_10K_P_01",),
            )
            assert cur.fetchone()[0] == 1
            cur.execute(
                "SELECT COUNT(*) FROM sub_chunks sc "
                "JOIN parent_chunks pc ON sc.parent_id = pc.id "
                "WHERE pc.id = %s",
                ("TEST_2099_10K_P_01",),
            )
            assert cur.fetchone()[0] == 2
            cur.execute(
                "SELECT COUNT(*) FROM sub_chunks sc "
                "JOIN parent_chunks pc ON sc.parent_id = pc.id "
                "WHERE pc.id = %s AND sc.embedding IS NULL",
                ("TEST_2099_10K_P_01",),
            )
            assert cur.fetchone()[0] == 2
            cur.execute(
                "DELETE FROM parent_chunks WHERE ticker = %s AND year = %s",
                ("TEST", 2099),
            )
            cur.execute(
                "DELETE FROM documents WHERE ticker = %s AND year = %s",
                ("TEST", 2099),
            )
        conn.commit()


@pytest.mark.skipif(not get_database_url(), reason="DATABASE_URL not set")
def test_postgres_store_reingest_same_filing():
    """Re-fetch same ticker/year/doctype must not FK-fail on document_id update."""
    import psycopg

    store = PostgresVectorStore()
    first = _sample_result()
    store.ingest(first)
    second = _sample_result()
    second.document_id = str(uuid.uuid4())
    second.chunk_plan.document_id = second.document_id
    store.ingest(second)

    url = get_database_url()
    assert url
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT document_id::text FROM documents WHERE ticker = %s AND year = %s",
                ("TEST", 2099),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == second.document_id
            cur.execute(
                "DELETE FROM parent_chunks WHERE ticker = %s AND year = %s",
                ("TEST", 2099),
            )
            cur.execute(
                "DELETE FROM documents WHERE ticker = %s AND year = %s",
                ("TEST", 2099),
            )
        conn.commit()


@pytest.mark.skipif(not get_database_url(), reason="DATABASE_URL not set")
def test_load_chunk_plan_from_db_roundtrip():
    from homework.rag_markitdown.postgres_read import load_chunk_plan_from_db

    store = PostgresVectorStore()
    result = _sample_result()
    store.ingest(result)
    try:
        plan = load_chunk_plan_from_db(result.document_id)
        assert plan is not None
        assert plan.ticker == "TEST"
        assert plan.year == 2099
        assert plan.parent_count == 1
        assert plan.subchunk_count == 2
        assert plan.parent_chunks[0].id == "TEST_2099_10K_P_01"
        assert len(plan.parent_chunks[0].subchunks) == 2
    finally:
        import psycopg

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


@pytest.mark.skipif(not get_database_url(), reason="DATABASE_URL not set")
def test_schema_is_ready():
    import psycopg

    url = get_database_url()
    assert url
    with psycopg.connect(url) as conn:
        assert schema_is_ready(conn)
