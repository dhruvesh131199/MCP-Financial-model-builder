"""Tests for query_rag step timing helper."""

from __future__ import annotations

from helper.rag.query_timing import QueryTimingSession


def test_format_summary_retrieve():
    session = QueryTimingSession(
        mode="retrieve",
        ticker="AAPL",
        loop=1,
        query="What are the main risk factors?",
        embed_provider="openrouter",
        embed_model="openai/text-embedding-3-small",
        embed_dim=1536,
    )
    session.record("query_embed", 0.12)
    session.record("semantic_search", 0.05)
    session.record("rerank", 1.80)
    session.record("load_parent", 0.02)
    session.finish()
    text = session.format_summary()
    assert "=== RAG query timing (retrieve) ===" in text
    assert "ticker=AAPL" in text
    assert "loop=1" in text
    assert 'query="What are the main risk factors?"' in text
    assert "provider=openrouter" in text
    assert "model=openai/text-embedding-3-small" in text
    assert "dim=1536" in text
    assert "query_embed=0.12s" in text
    assert "semantic_search=0.05s" in text
    assert "rerank=1.80s" in text
    assert "load_parent=0.02s" in text
    assert "total=" in text


def test_format_summary_finalize():
    session = QueryTimingSession(mode="finalize", ticker="NVDA")
    session.record("build_context", 0.01)
    session.finish()
    text = session.format_summary()
    assert "=== RAG query timing (finalize) ===" in text
    assert "build_context=0.01s" in text
