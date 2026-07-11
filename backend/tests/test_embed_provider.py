"""Tests for EmbedProvider factory."""

from __future__ import annotations

import pytest

from helper.postgres.embedding import (
    get_embed_provider,
    reset_embed_provider,
    vector_to_pg_literal,
)
from helper.postgres.hf_embed import EXPECTED_DIMENSION, HuggingFaceEmbedProvider
from helper.postgres.openrouter_embed import OpenRouterEmbedProvider


def test_default_provider_is_huggingface(monkeypatch):
    monkeypatch.delenv("EMBED_PROVIDER", raising=False)
    reset_embed_provider()
    provider = get_embed_provider()
    assert isinstance(provider, HuggingFaceEmbedProvider)
    assert provider.dimension == EXPECTED_DIMENSION
    reset_embed_provider()


def test_openrouter_provider_loads(monkeypatch):
    monkeypatch.setenv("EMBED_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    reset_embed_provider()
    provider = get_embed_provider()
    assert isinstance(provider, OpenRouterEmbedProvider)
    assert provider.dimension == 1536
    reset_embed_provider()


def test_openrouter_parse_and_embed_mocked(monkeypatch):
    monkeypatch.setenv("EMBED_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_EMBED_DIMENSION", "3")
    reset_embed_provider()

    class _Resp:
        status_code = 200
        text = ""

        def json(self):
            return {
                "data": [
                    {"index": 0, "embedding": [0.1, 0.2, 0.3]},
                    {"index": 1, "embedding": [0.4, 0.5, 0.6]},
                ]
            }

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            return _Resp()

    monkeypatch.setattr("helper.postgres.openrouter_embed.httpx.Client", _Client)
    provider = get_embed_provider()
    out = provider.embed_texts(["a", "b"])
    assert out == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    reset_embed_provider()
    monkeypatch.delenv("OPENROUTER_EMBED_DIMENSION", raising=False)


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("EMBED_PROVIDER", "nope")
    reset_embed_provider()
    with pytest.raises(ValueError, match="Unknown EMBED_PROVIDER"):
        get_embed_provider()
    reset_embed_provider()


def test_vector_to_pg_literal():
    assert vector_to_pg_literal([0.1, 0.2]) == "[0.10000000,0.20000000]"


def test_embed_batch_size_defaults(monkeypatch):
    from helper.postgres.embedding import get_embed_batch_size

    monkeypatch.delenv("EMBED_BATCH_SIZE", raising=False)
    monkeypatch.setenv("EMBED_PROVIDER", "huggingface")
    assert get_embed_batch_size() == 32

    monkeypatch.setenv("EMBED_PROVIDER", "openrouter")
    assert get_embed_batch_size() == 64

    monkeypatch.setenv("EMBED_BATCH_SIZE", "96")
    assert get_embed_batch_size() == 96

