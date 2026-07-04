"""Tests for RAG retrieve homework (mocked HF + Postgres)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from homework.rag_markitdown.hf_rerank import RerankHit, _parse_rerank_scores, rerank_hits
from homework.rag_markitdown.postgres_search import VectorHit
from homework.rag_markitdown.retrieve_homework.report import RetrieveTestReport, write_report


def _sample_hits(n: int = 3) -> list[VectorHit]:
    return [
        VectorHit(
            sub_id=f"sub-{i}",
            parent_id=f"NVDA_2025_10K_P_{i:02d}",
            content=f"chunk text {i}",
            chunk_index=i,
            vector_score=0.9 - i * 0.1,
            vector_rank=i + 1,
        )
        for i in range(n)
    ]


def test_parse_rerank_scores_flat_list():
    assert _parse_rerank_scores([0.9, 0.5, 0.2], 3) == [0.9, 0.5, 0.2]


def test_parse_rerank_scores_indexed():
    data = [{"index": 2, "score": 0.1}, {"index": 0, "score": 0.9}, {"index": 1, "score": 0.5}]
    assert _parse_rerank_scores(data, 3) == [0.9, 0.5, 0.1]


def test_rerank_hits_rank_delta():
    hits = _sample_hits(3)
    with patch("homework.rag_markitdown.hf_rerank.get_hf_token", return_value="hf_test"):
        with patch("homework.rag_markitdown.hf_rerank.httpx.Client") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [0.2, 0.95, 0.5]
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            reranked = rerank_hits("risk factors", hits)

    assert len(reranked) == 3
    assert reranked[0].sub_id == "sub-1"
    assert reranked[0].rerank_rank == 1
    assert reranked[0].vector_rank == 2
    assert reranked[0].rank_delta == 1


def test_report_html_has_both_stages(tmp_path):
    hits = _sample_hits(2)
    reranked = [
        RerankHit(
            sub_id=h.sub_id,
            parent_id=h.parent_id,
            content=h.content,
            chunk_index=h.chunk_index,
            vector_score=h.vector_score,
            vector_rank=h.vector_rank,
            rerank_score=0.8,
            rerank_rank=1,
            rank_delta=h.vector_rank - 1,
        )
        for h in hits
    ]
    report = RetrieveTestReport(
        query="test query",
        embed_model="BAAI/bge-base-en-v1.5",
        rerank_model="BAAI/bge-reranker-v2-m3",
        ticker="NVDA",
        year=2025,
        doctype="10K",
        vector_limit=25,
        vector_hit_count=2,
        created_at="2026-01-01T00:00:00+00:00",
        vector_hits=hits,
        reranked_hits=reranked,
    )
    write_report(tmp_path, report)
    html = (tmp_path / "retrieve_test_report.html").read_text(encoding="utf-8")
    assert "Stage 1 — Vector retrieval" in html
    assert "Stage 2 — After reranking" in html
    assert "test query" in html


@patch("homework.rag_markitdown.postgres_search.psycopg")
@patch("homework.rag_markitdown.postgres_search.schema_is_ready", return_value=True)
@patch("homework.rag_markitdown.postgres_search.get_database_url", return_value="postgresql://x")
def test_search_sub_chunks_maps_rows(mock_db_url, mock_schema, mock_psycopg):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ("sub-1", "P_01", "hello world", 0, 0.88),
        ("sub-2", "P_02", "other text", 1, 0.77),
    ]
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_psycopg.connect.return_value = mock_conn

    from homework.rag_markitdown.postgres_search import search_sub_chunks

    hits = search_sub_chunks([0.1] * 768, ticker="NVDA", year=2025, limit=25)

    assert len(hits) == 2
    assert hits[0].vector_rank == 1
    assert hits[0].vector_score == pytest.approx(0.88)
    assert hits[1].sub_id == "sub-2"


@pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").strip()
    or not (
        os.getenv("HF_TOKEN", "").strip()
        or os.getenv("HUGGINGFACE_API_KEY", "").strip()
    ),
    reason="DATABASE_URL and HF_TOKEN required for live retrieve test",
)
def test_retrieve_live_smoke():
    from homework.rag_markitdown.hf_embed import embed_texts, get_embed_model
    from homework.rag_markitdown.hf_rerank import get_rerank_model, rerank_hits
    from homework.rag_markitdown.postgres_search import resolve_latest_filing_year, search_sub_chunks

    year = resolve_latest_filing_year("NVDA")
    assert year is not None
    query = "What are the principal risk factors?"
    vec = embed_texts([query], model_id=get_embed_model())[0]
    hits = search_sub_chunks(vec, ticker="NVDA", year=year, limit=5)
    assert hits
    reranked = rerank_hits(query, hits, model_id=get_rerank_model())
    assert len(reranked) == len(hits)
