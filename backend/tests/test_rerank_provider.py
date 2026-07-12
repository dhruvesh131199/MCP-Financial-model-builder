"""Tests for RerankProvider factory + OpenRouter parse (mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from helper.postgres.hf_rerank import HuggingFaceRerankProvider
from helper.postgres.openrouter_rerank import (
    OpenRouterRerankError,
    OpenRouterRerankProvider,
    _parse_rerank_scores,
)
from helper.postgres.reranking import get_rerank_provider, reset_rerank_provider


def test_default_rerank_provider_is_huggingface(monkeypatch):
    monkeypatch.delenv("RERANK_PROVIDER", raising=False)
    reset_rerank_provider()
    provider = get_rerank_provider()
    assert isinstance(provider, HuggingFaceRerankProvider)
    assert "bge-reranker" in provider.model_id
    reset_rerank_provider()


def test_openrouter_rerank_provider_loads(monkeypatch):
    monkeypatch.setenv("RERANK_PROVIDER", "openrouter")
    reset_rerank_provider()
    provider = get_rerank_provider()
    assert isinstance(provider, OpenRouterRerankProvider)
    assert provider.model_id == "cohere/rerank-v3.5"
    reset_rerank_provider()


def test_unknown_rerank_provider_raises(monkeypatch):
    monkeypatch.setenv("RERANK_PROVIDER", "nope")
    reset_rerank_provider()
    with pytest.raises(ValueError, match="Unknown RERANK_PROVIDER"):
        get_rerank_provider()
    reset_rerank_provider()


def test_parse_rerank_scores_indexed():
    data = {
        "results": [
            {"index": 2, "relevance_score": 0.1},
            {"index": 0, "relevance_score": 0.9},
            {"index": 1, "relevance_score": 0.5},
        ]
    }
    assert _parse_rerank_scores(data, 3) == [0.9, 0.5, 0.1]


def test_parse_rerank_scores_incomplete_raises():
    data = {"results": [{"index": 0, "relevance_score": 0.9}]}
    with pytest.raises(OpenRouterRerankError, match="incomplete"):
        _parse_rerank_scores(data, 3)


def test_openrouter_score_mocked_http(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    provider = OpenRouterRerankProvider()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"index": 1, "relevance_score": 0.95},
            {"index": 0, "relevance_score": 0.2},
            {"index": 2, "relevance_score": 0.5},
        ]
    }
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("helper.postgres.openrouter_rerank.httpx.Client", return_value=mock_client):
        scores = provider.score("q", ["a", "b", "c"])

    assert scores == [0.2, 0.95, 0.5]
    call_kwargs = mock_client.post.call_args
    payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert payload["documents"] == ["a", "b", "c"]
    assert payload["top_n"] == 3
    assert payload["query"] == "q"
