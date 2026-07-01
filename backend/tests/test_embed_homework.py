"""Tests for RAG embed homework (mocked HF; optional live integration)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import os
import pytest

from homework.rag_markitdown.embed_homework.hf_embed_client import (
    EXPECTED_DIMENSION,
    HuggingFaceEmbedError,
    _normalize_embedding,
    embed_texts,
)
from homework.rag_markitdown.hf_embed import embed_texts as prod_embed_texts
from homework.rag_markitdown.embed_homework.run_embed_test import (
    load_subchunks_from_fixture,
    resolve_chunks_path,
)
from homework.rag_markitdown.embed_homework.similarity import (
    cosine_similarity,
    rank_by_similarity,
)


def test_homework_reexports_production_embed_client():
    assert embed_texts is prod_embed_texts


def test_normalize_embedding_sentence_level():
    raw = [0.1, 0.2, 0.3]
    assert _normalize_embedding(raw) == [0.1, 0.2, 0.3]


def test_normalize_embedding_token_level_mean_pool():
    raw = [[1.0, 0.0], [0.0, 1.0]]
    assert _normalize_embedding(raw) == [0.5, 0.5]


def test_cosine_similarity_identical():
    v = [1.0, 0.0, 0.0]
    assert cosine_similarity(v, v) == pytest.approx(1.0)


def test_rank_by_similarity():
    query = [1.0, 0.0, 0.0]
    chunks = [
        [0.0, 1.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.7, 0.7, 0.0],
    ]
    ranked = rank_by_similarity(query, chunks, top_k=2)
    assert ranked[0] == (1, pytest.approx(1.0))
    assert ranked[1][0] == 2


def test_fixture_produces_subchunks():
    rows, source = load_subchunks_from_fixture()
    assert len(rows) >= 3
    assert "fixture:" in source
    assert all(r.content for r in rows)


def test_resolve_chunks_path_by_ticker(tmp_path, monkeypatch):
    ingest_dir = tmp_path / "AAPL_old"
    ingest_dir.mkdir()
    (ingest_dir / "chunks.json").write_text("{}", encoding="utf-8")

    newer_dir = tmp_path / "AAPL_new"
    newer_dir.mkdir()
    chunks_file = newer_dir / "chunks.json"
    chunks_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "homework.rag_markitdown.embed_homework.run_embed_test.OUTPUT_ROOT",
        tmp_path,
    )

    resolved = resolve_chunks_path(None, ticker="AAPL")
    assert resolved == chunks_file


def test_resolve_chunks_path_glob(tmp_path, monkeypatch):
    d = tmp_path / "AAPL_20260101_120000"
    d.mkdir()
    chunks_file = d / "chunks.json"
    chunks_file.write_text("{}", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "homework.rag_markitdown.embed_homework.run_embed_test.OUTPUT_ROOT",
        tmp_path,
    )

    resolved = resolve_chunks_path("AAPL_*/chunks.json")
    assert resolved == chunks_file


@patch("homework.rag_markitdown.hf_embed.get_hf_token", return_value="hf_test")
@patch("homework.rag_markitdown.hf_embed.httpx.Client")
def test_embed_texts_mocked(mock_client_cls, _mock_token):
    mock_response = MagicMock()
    mock_response.status_code = 200
    dim = EXPECTED_DIMENSION
    mock_response.json.return_value = [
        [0.1] * dim,
        [0.2] * dim,
    ]
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    result = embed_texts(["hello", "world"], model_id="BAAI/bge-base-en-v1.5")
    assert len(result) == 2
    assert len(result[0]) == EXPECTED_DIMENSION
    mock_client.post.assert_called_once()


@patch("homework.rag_markitdown.hf_embed.get_hf_token", return_value="hf_test")
@patch("homework.rag_markitdown.hf_embed.httpx.Client")
def test_embed_texts_single_input(mock_client_cls, _mock_token):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [0.1] * EXPECTED_DIMENSION
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    result = embed_texts(["one chunk"], model_id="BAAI/bge-base-en-v1.5")
    assert len(result) == 1
    assert len(result[0]) == EXPECTED_DIMENSION


@patch("homework.rag_markitdown.hf_embed.get_hf_token", return_value="hf_test")
@patch("homework.rag_markitdown.hf_embed.httpx.Client")
def test_embed_texts_429(mock_client_cls, _mock_token):
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "rate limit"
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    with pytest.raises(HuggingFaceEmbedError, match="429"):
        embed_texts(["test"], model_id="BAAI/bge-base-en-v1.5")


@pytest.mark.skipif(
    not os.getenv("HF_TOKEN", "").strip()
    and not os.getenv("HUGGINGFACE_API_KEY", "").strip(),
    reason="HF_TOKEN not set",
)
def test_embed_texts_live():
    vectors = embed_texts(["risk factors in supply chain", "revenue growth"])
    assert len(vectors) == 2
    assert len(vectors[0]) == EXPECTED_DIMENSION
