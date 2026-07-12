"""Live OpenRouter rerank smoke — real HTTP round-trip (skips without API key)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from helper.postgres.openrouter_rerank import OpenRouterRerankProvider
from helper.postgres.reranking import reset_rerank_provider
from services.rag_rerank import rerank_hits
from services.rag_vector_search import VectorHit

# Load backend/.env so local OPENROUTER_API_KEY is available without exporting.
_env_path = Path(__file__).resolve().parents[1] / ".env"
if _env_path.is_file():
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_path)
    except ImportError:
        pass

_HAS_KEY = bool(
    os.getenv("OPENROUTER_API_KEY", "").strip()
    or os.getenv("OPENAI_API_KEY", "").strip()
)

DOC_PARIS = "Paris is the capital of France."
DOC_BANANA = "Bananas are yellow fruit."
DOC_BERLIN = "Berlin is in Germany."
DOCS = [DOC_PARIS, DOC_BANANA, DOC_BERLIN]


@pytest.mark.skipif(not _HAS_KEY, reason="OPENROUTER_API_KEY not set")
def test_openrouter_rerank_live_round_trip():
    reset_rerank_provider()
    provider = OpenRouterRerankProvider()
    scores = provider.score("capital of France", DOCS)

    assert len(scores) == 3
    assert all(isinstance(s, float) for s in scores)
    assert scores[0] == max(scores), (
        f"Paris passage should rank highest; got scores={scores}"
    )


@pytest.mark.skipif(not _HAS_KEY, reason="OPENROUTER_API_KEY not set")
def test_openrouter_rerank_hits_facade_live(monkeypatch):
    monkeypatch.setenv("RERANK_PROVIDER", "openrouter")
    reset_rerank_provider()

    hits = [
        VectorHit(
            sub_id=f"sub-{i}",
            parent_id=f"P_{i}",
            content=text,
            chunk_index=i,
            vector_score=0.5,
            vector_rank=i + 1,
            document_id="doc",
            ticker="TEST",
            year=2025,
            doctype="10K",
        )
        for i, text in enumerate(DOCS)
    ]
    ranked = rerank_hits("capital of France", hits)
    assert ranked[0].content == DOC_PARIS
    assert ranked[0].rerank_rank == 1
    reset_rerank_provider()
