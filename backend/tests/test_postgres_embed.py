"""Tests for postgres_embed (mocked HF)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from homework.rag_markitdown.hf_embed import EXPECTED_DIMENSION
from homework.rag_markitdown.postgres_embed import count_unembedded, embed_document


def _fake_vector(seed: float = 0.1) -> list[float]:
    return [seed] * EXPECTED_DIMENSION


@pytest.mark.skipif(
    not __import__("os").getenv("DATABASE_URL"),
    reason="DATABASE_URL not set",
)
@patch("homework.rag_markitdown.postgres_embed.embed_texts")
def test_embed_document_batches_and_updates(mock_embed):
    import psycopg

    from homework.rag_markitdown.db import get_database_url
    from homework.rag_markitdown.postgres_store import PostgresVectorStore
    from homework.rag_markitdown.schema import (
        ChunkPlan,
        DocumentSource,
        IngestResult,
        ParentChunk,
        SourceFormat,
        SubChunk,
    )

    sub_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    parent = ParentChunk(
        id="EMBED_2099_10K_P_01",
        ticker="EMBED",
        year=2099,
        doctype="10K",
        chunk_index=1,
        content="parent",
        char_count=6,
        approx_tokens=2,
        subchunks=[
            SubChunk(id=sub_ids[0], parent_id="EMBED_2099_10K_P_01", content="one", embedding=None),
            SubChunk(id=sub_ids[1], parent_id="EMBED_2099_10K_P_01", content="two", embedding=None),
        ],
    )
    plan = ChunkPlan(
        document_id=str(uuid.uuid4()),
        ticker="EMBED",
        year=2099,
        doctype="10K",
        parent_chunks=[parent],
        parent_count=1,
        subchunk_count=2,
    )
    result = IngestResult(
        document_id=plan.document_id,
        source=DocumentSource.MANUAL_UPLOAD,
        source_format=SourceFormat.HTML,
        raw_filename="raw.html",
        raw_bytes=10,
        markdown_chars=10,
        markdown_lines=1,
        output_dir="/tmp",
        raw_path="/tmp/raw.html",
        markdown_path="/tmp/converted.md",
        meta_path="/tmp/meta.json",
        report_html_path="/tmp/report.html",
        chunk_plan=plan,
    )

    mock_embed.return_value = [_fake_vector(0.1), _fake_vector(0.2)]

    url = get_database_url()
    assert url
    with psycopg.connect(url) as conn:
        with conn.transaction():
            PostgresVectorStore()._upsert_filing(conn, result)

    assert count_unembedded(result.document_id) == 2
    stats = embed_document(result.document_id)
    assert stats.embedded_count == 2
    assert stats.model_id
    assert count_unembedded(result.document_id) == 0
    mock_embed.assert_called_once()
    texts = mock_embed.call_args[0][0]
    assert set(texts) == {"one", "two"}

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM sub_chunks sc
                JOIN parent_chunks pc ON sc.parent_id = pc.id
                WHERE pc.document_id = %s AND sc.embedding IS NOT NULL
                """,
                (uuid.UUID(result.document_id),),
            )
            assert cur.fetchone()[0] == 2
            cur.execute(
                "DELETE FROM parent_chunks WHERE ticker = %s AND year = %s",
                ("EMBED", 2099),
            )
            cur.execute(
                "DELETE FROM documents WHERE ticker = %s AND year = %s",
                ("EMBED", 2099),
            )
        conn.commit()
