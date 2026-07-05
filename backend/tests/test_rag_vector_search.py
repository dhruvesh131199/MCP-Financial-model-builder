"""Tests for global RAG vector search."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.rag_vector_search import load_parent_chunk, search_sub_chunks_global


@patch("services.rag_vector_search.psycopg")
@patch("services.rag_vector_search.schema_is_ready", return_value=True)
@patch("services.rag_vector_search.get_database_url", return_value="postgresql://x")
def test_search_sub_chunks_global_maps_rows(mock_db_url, mock_schema, mock_psycopg):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ("sub-1", "P_01", "hello world", 0, "doc-uuid", "NVDA", 2025, "10K", "https://sec.gov", 0.88),
        ("sub-2", "P_02", "other text", 1, "doc-uuid", "NVDA", 2025, "10K", None, 0.77),
    ]
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_psycopg.connect.return_value = mock_conn

    hits = search_sub_chunks_global([0.1] * 768, limit=10)

    assert len(hits) == 2
    assert hits[0].vector_rank == 1
    assert hits[0].vector_score == pytest.approx(0.88)
    assert hits[0].ticker == "NVDA"
    assert hits[0].document_id == "doc-uuid"
    sql = mock_cursor.execute.call_args[0][0]
    assert "NOT IN" not in sql


@patch("services.rag_vector_search.psycopg")
@patch("services.rag_vector_search.schema_is_ready", return_value=True)
@patch("services.rag_vector_search.get_database_url", return_value="postgresql://x")
def test_search_filters_by_ticker(mock_db_url, mock_schema, mock_psycopg):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_psycopg.connect.return_value = mock_conn

    search_sub_chunks_global([0.1] * 768, limit=10, ticker="nvda")

    sql = mock_cursor.execute.call_args[0][0]
    assert "pc.ticker = %s" in sql
    params = mock_cursor.execute.call_args[0][1]
    assert "NVDA" in params


@patch("services.rag_vector_search.psycopg")
@patch("services.rag_vector_search.schema_is_ready", return_value=True)
@patch("services.rag_vector_search.get_database_url", return_value="postgresql://x")
def test_search_excludes_collected_parents(mock_db_url, mock_schema, mock_psycopg):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_psycopg.connect.return_value = mock_conn

    search_sub_chunks_global(
        [0.1] * 768,
        limit=10,
        exclude_parent_ids=["NVDA_2025_10K_P_01", "NVDA_2025_10K_P_02"],
    )

    sql = mock_cursor.execute.call_args[0][0]
    assert "NOT IN" in sql
    params = mock_cursor.execute.call_args[0][1]
    assert "NVDA_2025_10K_P_01" in params
    assert "NVDA_2025_10K_P_02" in params


@patch("services.rag_vector_search.psycopg")
@patch("services.rag_vector_search.schema_is_ready", return_value=True)
@patch("services.rag_vector_search.get_database_url", return_value="postgresql://x")
def test_load_parent_chunk(mock_db_url, mock_schema, mock_psycopg):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (
        "NVDA_2025_10K_P_01",
        "doc-uuid",
        "NVDA",
        2025,
        "10K",
        1,
        "full parent text",
        5000,
        1250,
        "https://sec.gov",
    )
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_psycopg.connect.return_value = mock_conn

    row = load_parent_chunk("NVDA_2025_10K_P_01")
    assert row is not None
    assert row["parent_id"] == "NVDA_2025_10K_P_01"
    assert row["char_count"] == 5000
    assert row["content"] == "full parent text"
