"""Tests for query_rag Processing sidebar progress (retrieve + finalize)."""

from __future__ import annotations

from unittest.mock import patch

import store as store_module
from services.rag_loop_retrieval import finalize_loop, retrieve_loop
from services.rag_rerank import RerankHit
from services.rag_vector_search import VectorHit
from session_process_store import (
    RAG_QUERY_FINALIZE_PROCESS_NAME,
    RagQueryFinalizeProgress,
    RagQueryRetrieveProgress,
    list_processes,
    query_rag_process_name,
    truncate_process_name,
)
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


def test_truncate_process_name():
    assert truncate_process_name("short") == "short"
    long = "x" * 600
    out = truncate_process_name(long, max_len=500)
    assert len(out) == 500
    assert out.endswith("…")


def test_query_rag_process_name_prefix():
    assert query_rag_process_name("NVDA supply chain") == "Query: NVDA supply chain"
    assert query_rag_process_name("  spaced  ") == "Query: spaced"


def test_retrieve_progress_helper_start_set_finish():
    sid = create_session()
    prog = RagQueryRetrieveProgress.start(
        sid, source="mcp", process_name=query_rag_process_name("NVDA supply chain risks")
    )
    listed = list_processes(sid)
    assert len(listed) == 1
    assert listed[0]["process_name"] == "Query: NVDA supply chain risks"
    assert listed[0]["progress"] == 2

    prog.set("Semantic search on subchunks", 10)
    assert list_processes(sid)[0]["progress"] == 10
    prog.set("Reranking sub chunks", 30)
    assert list_processes(sid)[0]["progress"] == 30
    prog.set("Analyzing parent chunk abc", 100)
    assert list_processes(sid)[0]["progress"] == 100

    prog.finish()
    listed = list_processes(sid)
    assert len(listed) == 1
    assert listed[0].get("expires_at")


def test_finalize_progress_helper_0_to_100():
    sid = create_session()
    prog = RagQueryFinalizeProgress.start(sid, source="mcp")
    listed = list_processes(sid)
    assert listed[0]["process_name"] == RAG_QUERY_FINALIZE_PROCESS_NAME
    assert listed[0]["progress"] == 0
    prog.finish()
    listed = list_processes(sid)
    assert listed[0].get("expires_at")


def test_retrieve_loop_progress_10_30_100_and_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()

    parent1 = _parent_row("NVDA_2025_10K_P_01", 1, "Item 1A risks text")
    query = "NVDA supply chain risks"

    upsert_calls: list[dict] = []
    delete_ids: list[str] = []

    real_start = RagQueryRetrieveProgress.start

    def tracking_start(session_id, *, source, process_name, message="Starting…"):
        prog = real_start(
            session_id, source=source, process_name=process_name, message=message
        )
        orig_set = prog.set
        orig_finish = prog.finish
        orig_abandon = prog.abandon

        def set_track(message: str, progress: float) -> None:
            upsert_calls.append(
                {
                    "process_name": prog.process_name,
                    "message": message,
                    "progress": progress,
                    "process_id": prog.process_id,
                }
            )
            orig_set(message, progress)

        def finish_track(message: str | None = None) -> None:
            delete_ids.append(prog.process_id)
            orig_finish(message)

        def abandon_track() -> None:
            delete_ids.append(prog.process_id)
            orig_abandon()

        prog.set = set_track  # type: ignore[method-assign]
        prog.finish = finish_track  # type: ignore[method-assign]
        prog.abandon = abandon_track  # type: ignore[method-assign]
        return prog

    with patch(
        "services.rag_loop_retrieval.RagQueryRetrieveProgress.start",
        side_effect=tracking_start,
    ):
        with patch(
            "services.rag_loop_retrieval.embed_texts", return_value=[[0.1] * 768]
        ):
            with patch(
                "services.rag_loop_retrieval.search_sub_chunks_global",
                return_value=[_vector_hit("NVDA_2025_10K_P_01", "sub-a", 1)],
            ):
                with patch(
                    "services.rag_loop_retrieval.rerank_hits",
                    return_value=[_rerank_hit("NVDA_2025_10K_P_01", "sub-a", 1, 1)],
                ):
                    with patch(
                        "services.rag_loop_retrieval.load_parent_chunk",
                        return_value=parent1,
                    ):
                        result = retrieve_loop(sid, query, ticker="NVDA")

    assert result["mode"] == "retrieve"
    assert result["loop"] == 1

    progresses = [c["progress"] for c in upsert_calls]
    assert progresses == [10, 30, 100]
    assert upsert_calls[0]["message"] == "Semantic search on subchunks"
    assert upsert_calls[1]["message"] == "Reranking sub chunks"
    assert "Analyzing parent chunk NVDA_2025_10K_P_01" in upsert_calls[2]["message"]
    assert all(c["process_name"] == f"Query: {query}" for c in upsert_calls)
    assert len(delete_ids) == 1


def test_second_retrieve_creates_new_process(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()

    parent1 = _parent_row("NVDA_2025_10K_P_01", 1, "Item 1A risks text")
    parent2 = _parent_row("NVDA_2025_10K_P_07", 7, "Item 2 manufacturing text")

    process_ids: list[str] = []
    real_start = RagQueryRetrieveProgress.start

    def tracking_start(session_id, *, source, process_name, message="Starting…"):
        prog = real_start(
            session_id, source=source, process_name=process_name, message=message
        )
        process_ids.append(prog.process_id)
        return prog

    with patch(
        "services.rag_loop_retrieval.RagQueryRetrieveProgress.start",
        side_effect=tracking_start,
    ):
        with patch(
            "services.rag_loop_retrieval.embed_texts", return_value=[[0.1] * 768]
        ):
            with patch(
                "services.rag_loop_retrieval.search_sub_chunks_global",
                side_effect=[
                    [_vector_hit("NVDA_2025_10K_P_01", "sub-a", 1)],
                    [_vector_hit("NVDA_2025_10K_P_07", "sub-b", 1)],
                ],
            ):
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
                        retrieve_loop(
                            sid, "NVDA supply chain risks", ticker="NVDA"
                        )
                        retrieve_loop(sid, "NVDA Item 2 manufacturing")

    assert len(process_ids) == 2
    assert process_ids[0] != process_ids[1]


def test_finalize_loop_progress_and_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()

    parent1 = _parent_row("NVDA_2025_10K_P_01", 1, "Item 1A risks text")

    with patch(
        "services.rag_loop_retrieval.embed_texts", return_value=[[0.1] * 768]
    ):
        with patch(
            "services.rag_loop_retrieval.search_sub_chunks_global",
            return_value=[_vector_hit("NVDA_2025_10K_P_01", "sub-a", 1)],
        ):
            with patch(
                "services.rag_loop_retrieval.rerank_hits",
                return_value=[_rerank_hit("NVDA_2025_10K_P_01", "sub-a", 1, 1)],
            ):
                with patch(
                    "services.rag_loop_retrieval.load_parent_chunk",
                    return_value=parent1,
                ):
                    retrieve_loop(sid, "NVDA risks", ticker="NVDA")

    finish_called = {"ok": False}
    real_finish = RagQueryFinalizeProgress.finish

    def finish_track(self, message: str = "Done…") -> None:
        finish_called["ok"] = True
        assert self.process_id
        real_finish(self, message=message)

    with patch.object(RagQueryFinalizeProgress, "finish", finish_track):
        fin = finalize_loop(sid)

    assert fin["parent_count"] == 1
    assert finish_called["ok"] is True


def test_retrieve_exhausted_abandons_process(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()

    abandoned = {"ok": False}
    real_start = RagQueryRetrieveProgress.start

    def tracking_start(session_id, *, source, process_name, message="Starting…"):
        prog = real_start(
            session_id, source=source, process_name=process_name, message=message
        )
        orig_abandon = prog.abandon

        def abandon_track() -> None:
            abandoned["ok"] = True
            orig_abandon()

        prog.abandon = abandon_track  # type: ignore[method-assign]
        return prog

    with patch(
        "services.rag_loop_retrieval.RagQueryRetrieveProgress.start",
        side_effect=tracking_start,
    ):
        with patch(
            "services.rag_loop_retrieval.embed_texts", return_value=[[0.1] * 768]
        ):
            with patch(
                "services.rag_loop_retrieval.search_sub_chunks_global",
                return_value=[],
            ):
                result = retrieve_loop(sid, "empty query", ticker="NVDA")

    assert result["exhausted"] is True
    assert abandoned["ok"] is True


def test_ticker_required_skips_process(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()

    with patch(
        "services.rag_loop_retrieval.RagQueryRetrieveProgress.start"
    ) as mock_start:
        result = retrieve_loop(sid, "some query")
    assert result["error"] == "ticker_required"
    mock_start.assert_not_called()
