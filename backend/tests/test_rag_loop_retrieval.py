"""Tests for loop RAG retrieval service."""

from __future__ import annotations

from unittest.mock import patch

import store as store_module
from rag_query_state import MAX_LOOPS, load_state, save_state, RagQueryState
from services.rag_loop_retrieval import finalize_loop, reset_loop, retrieve_loop
from services.rag_rerank import RerankHit
from services.rag_vector_search import VectorHit
from store import create_session


def _vector_hit(parent_id: str, sub_id: str, idx: int) -> VectorHit:
    return VectorHit(
        sub_id=sub_id,
        parent_id=parent_id,
        content=f"sub content {sub_id}",
        chunk_index=idx,
        vector_score=0.8,
        vector_rank=idx,
        document_id="doc-uuid",
        ticker="NVDA",
        year=2025,
        doctype="10K",
        document_source="https://sec.gov",
    )


def _rerank_hit(parent_id: str, sub_id: str, idx: int, rerank_rank: int) -> RerankHit:
    v = _vector_hit(parent_id, sub_id, idx)
    return RerankHit(
        sub_id=v.sub_id,
        parent_id=v.parent_id,
        content=v.content,
        chunk_index=v.chunk_index,
        vector_score=v.vector_score,
        vector_rank=v.vector_rank,
        rerank_score=0.9,
        rerank_rank=rerank_rank,
        rank_delta=v.vector_rank - rerank_rank,
        document_id=v.document_id,
        ticker=v.ticker,
        year=v.year,
        doctype=v.doctype,
        document_source=v.document_source,
    )


def _parent_row(parent_id: str, chunk_index: int, content: str) -> dict:
    return {
        "parent_id": parent_id,
        "document_id": "doc-uuid",
        "ticker": "NVDA",
        "year": 2025,
        "doctype": "10K",
        "chunk_index": chunk_index,
        "content": content,
        "char_count": len(content),
        "approx_tokens": len(content) // 4,
        "document_source": "https://sec.gov",
    }


def test_retrieve_loop1_requires_ticker(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()

    result = retrieve_loop(sid, "some query")
    assert result["error"] == "ticker_required"


def test_retrieve_finalize_multi_loop(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()

    parent1 = _parent_row("NVDA_2025_10K_P_01", 1, "Item 1A risks text")
    parent2 = _parent_row("NVDA_2025_10K_P_07", 7, "Item 2 manufacturing text")

    with patch("services.rag_loop_retrieval.embed_texts", return_value=[[0.1] * 768]):
        with patch(
            "services.rag_loop_retrieval.search_sub_chunks_global",
            side_effect=[
                [_vector_hit("NVDA_2025_10K_P_01", "sub-a", 1)],
                [_vector_hit("NVDA_2025_10K_P_07", "sub-b", 1)],
            ],
        ) as mock_search:
            with patch(
                "services.rag_loop_retrieval.rerank_hits",
                side_effect=[
                    [_rerank_hit("NVDA_2025_10K_P_01", "sub-a", 1, 1)],
                    [_rerank_hit("NVDA_2025_10K_P_07", "sub-b", 1, 1)],
                ],
            ):
                with patch(
                    "services.rag_loop_retrieval.load_parent_chunk",
                    side_effect=[parent1, parent2],
                ):
                    r1 = retrieve_loop(
                        sid,
                        "NVDA supply chain risks",
                        ticker="NVDA",
                        original_question="What are NVDA risks?",
                    )
                    r2 = retrieve_loop(sid, "NVDA Item 2 manufacturing")

    assert r1["mode"] == "retrieve"
    assert r1["ticker"] == "NVDA"
    assert r1["loop"] == 1
    assert mock_search.call_args_list[0].kwargs.get("ticker") == "NVDA"
    assert mock_search.call_args_list[1].kwargs.get("ticker") == "NVDA"

    assert r2["loop"] == 2
    assert r2["ticker"] == "NVDA"

    fin = finalize_loop(sid)
    assert fin["parent_count"] == 2
    assert fin["ticker"] == "NVDA"
    assert len(fin["citations"]) == 2
    assert fin["citations"][0]["label"] == "NVDA · 10-K · FY2025 · section #1"
    assert "Sources" in fin["message"]
    assert load_state(sid) is None


def test_ticker_mismatch_on_later_loop(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()

    save_state(sid, RagQueryState(ticker="NVDA", loops_completed=1))

    result = retrieve_loop(sid, "query", ticker="COST")
    assert result["error"] == "ticker_mismatch"


def test_retrieve_exhausted_when_no_hits(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()

    with patch("services.rag_loop_retrieval.embed_texts", return_value=[[0.1] * 768]):
        with patch("services.rag_loop_retrieval.search_sub_chunks_global", return_value=[]):
            result = retrieve_loop(sid, "some query", ticker="NVDA")

    assert result["exhausted"] is True
    assert result["loops_completed"] == 0
    assert result["ticker"] == "NVDA"


def test_max_loops_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()

    state = RagQueryState(loops_completed=MAX_LOOPS, ticker="NVDA")
    save_state(sid, state)

    result = retrieve_loop(sid, "another query")
    assert "error" in result
    assert result["suggest_mode"] == "finalize"


def test_reset_clears_state(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()
    save_state(sid, RagQueryState(loops_completed=1, ticker="NVDA"))

    result = reset_loop(sid)
    assert result["mode"] == "reset"
    assert load_state(sid) is None
