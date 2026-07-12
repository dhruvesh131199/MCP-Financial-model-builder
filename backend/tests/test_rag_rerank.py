"""Tests for RAG reranker facade + HF score parsing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from helper.postgres.hf_rerank import _parse_rerank_scores
from services.rag_rerank import RerankHit, rerank_hits
from services.rag_vector_search import VectorHit


def _sample_hits(n: int = 3) -> list[VectorHit]:
    return [
        VectorHit(
            sub_id=f"sub-{i}",
            parent_id=f"NVDA_2025_10K_P_{i:02d}",
            content=f"chunk text {i}",
            chunk_index=i,
            vector_score=0.9 - i * 0.1,
            vector_rank=i + 1,
            document_id="doc-uuid",
            ticker="NVDA",
            year=2025,
            doctype="10K",
            document_source="https://sec.gov",
        )
        for i in range(n)
    ]


def test_parse_rerank_scores_flat_list():
    assert _parse_rerank_scores([0.9, 0.5, 0.2], 3) == [0.9, 0.5, 0.2]


def test_parse_rerank_scores_indexed():
    data = [
        {"index": 2, "score": 0.1},
        {"index": 0, "score": 0.9},
        {"index": 1, "score": 0.5},
    ]
    assert _parse_rerank_scores(data, 3) == [0.9, 0.5, 0.1]


def test_rerank_hits_rank_delta_and_metadata():
    hits = _sample_hits(3)
    mock_provider = MagicMock()
    mock_provider.score.return_value = [0.2, 0.95, 0.5]
    with patch("services.rag_rerank.get_rerank_provider", return_value=mock_provider):
        reranked = rerank_hits("risk factors", hits)

    assert len(reranked) == 3
    assert isinstance(reranked[0], RerankHit)
    assert reranked[0].sub_id == "sub-1"
    assert reranked[0].rerank_rank == 1
    assert reranked[0].vector_rank == 2
    assert reranked[0].rank_delta == 1
    assert reranked[0].ticker == "NVDA"
    assert reranked[0].document_id == "doc-uuid"
    mock_provider.score.assert_called_once()


def test_rerank_hits_hf_http_path():
    hits = _sample_hits(3)
    with patch("helper.postgres.hf_rerank.get_hf_token", return_value="hf_test"):
        with patch("helper.postgres.hf_rerank.httpx.Client") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [0.2, 0.95, 0.5]
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            with patch(
                "services.rag_rerank.get_rerank_provider",
                return_value=__import__(
                    "helper.postgres.hf_rerank", fromlist=["HuggingFaceRerankProvider"]
                ).HuggingFaceRerankProvider(),
            ):
                reranked = rerank_hits("risk factors", hits)

    assert reranked[0].sub_id == "sub-1"
    assert reranked[0].rerank_score == 0.95
