"""Host-driven loop RAG retrieval — retrieve, finalize, reset."""

from __future__ import annotations

from typing import Any

from helper.postgres.hf_embed import embed_texts
from rag_query_state import (
    ParentChunkRecord,
    RagQueryState,
    build_parent_record,
    clear_state,
    load_state,
    save_state,
)
from services.rag_rerank import RerankHit, rerank_hits
from services.rag_vector_search import load_parent_chunk, search_sub_chunks_global
from session_process_store import (
    RagQueryFinalizeProgress,
    RagQueryRetrieveProgress,
    query_rag_process_name,
)

FINALIZE_SEPARATOR = "\n\n---\n\n"


def _normalize_ticker(raw: str | None) -> str | None:
    if not raw or not raw.strip():
        return None
    return raw.strip().upper()


def _resolve_ticker_for_retrieve(
    state: RagQueryState,
    ticker: str | None,
) -> tuple[str | None, dict[str, Any] | None]:
    """Loop 1 requires ticker; later loops reuse state.ticker."""
    normalized = _normalize_ticker(ticker)
    if state.loops_completed == 0:
        if not normalized:
            return None, {
                "error": "ticker_required",
                "message": (
                    "Pass ticker on the first retrieve (e.g. NVDA). "
                    "Ingest that 10-K first via fetch_report(full_report)."
                ),
                "suggest_action": "pass_ticker_on_loop_1",
            }
        return normalized, None

    if normalized and state.ticker and normalized != state.ticker:
        return None, {
            "error": "ticker_mismatch",
            "message": (
                f"This run is scoped to {state.ticker}. "
                f"Got ticker={normalized}. Call reset and start a new run for a different ticker."
            ),
            "active_ticker": state.ticker,
            "provided_ticker": normalized,
        }

    if state.ticker:
        return state.ticker, None

    if normalized:
        return normalized, None

    return None, {
        "error": "ticker_required",
        "message": "No ticker in session state. Pass ticker on loop 1 or call reset.",
    }


def _citation_dict(parent: ParentChunkRecord) -> dict[str, Any]:
    return {
        "label": parent.citation_short(),
        "filing_key": parent.filing_key,
        "ticker": parent.ticker,
        "year": parent.year,
        "chunk_index": parent.chunk_index,
        "parent_id": parent.parent_id,
    }


def _get_or_create_state(session_id: str) -> RagQueryState:
    state = load_state(session_id)
    if state is None:
        state = RagQueryState()
    return state


def _pick_winning_hit(
    reranked: list[RerankHit],
    collected_ids: set[str],
) -> RerankHit | None:
    """Pick best reranked hit whose parent is not already collected."""
    for hit in reranked:
        if hit.parent_id not in collected_ids:
            return hit
    return None


def retrieve_loop(
    session_id: str,
    query: str,
    *,
    ticker: str | None = None,
    original_question: str | None = None,
    top_k: int = 10,
    source: str = "mcp",
) -> dict[str, Any]:
    """Run one host-driven retrieve loop with a Processing sidebar chip.

    Use when: MCP query_rag mode=retrieve.
    Logic: after guards → new process (name=query) → embed → search@10 → rerank@30 →
    load parent@100 → save state → finish/delete chip.
    Returns: retrieve payload with new_parent, or exhausted/error dict.
    """
    query = query.strip()
    if not query:
        return {"error": "query is required for retrieve mode"}

    state = _get_or_create_state(session_id)

    if state.loops_completed >= state.max_loops:
        return {
            "error": f"Maximum loops ({state.max_loops}) reached",
            "suggest_mode": "finalize",
            "loops_completed": state.loops_completed,
            "max_loops": state.max_loops,
        }

    active_ticker, ticker_err = _resolve_ticker_for_retrieve(state, ticker)
    if ticker_err:
        return ticker_err

    if original_question and not state.original_question:
        state.original_question = original_question.strip() or None

    if state.loops_completed == 0 and active_ticker:
        state.ticker = active_ticker

    progress: RagQueryRetrieveProgress | None = None
    finished = False
    try:
        progress = RagQueryRetrieveProgress.start(
            session_id,
            source=source,
            process_name=query_rag_process_name(query),
        )

        vectors = embed_texts([query])
        if not vectors:
            return {"error": "Failed to embed query"}

        collected_ids = set(state.collected_parent_ids)
        hits = search_sub_chunks_global(
            vectors[0],
            limit=top_k,
            ticker=active_ticker,
            exclude_parent_ids=list(collected_ids),
        )
        progress.set("Semantic search on subchunks", 10)

        if not hits:
            return {
                "mode": "retrieve",
                "ticker": active_ticker,
                "exhausted": True,
                "loops_completed": state.loops_completed,
                "max_loops": state.max_loops,
                "collected_parent_ids": state.collected_parent_ids,
                "parents_metadata": [p.metadata_summary() for p in state.parents],
                "message": (
                    f"No unseen parent chunks remain for {active_ticker} on this query. "
                    "Call finalize with collected context or ingest more 10-K filings."
                ),
            }

        reranked = rerank_hits(query, hits)
        progress.set("Reranking sub chunks", 30)
        winner = _pick_winning_hit(reranked, collected_ids)

        if winner is None:
            return {
                "mode": "retrieve",
                "ticker": active_ticker,
                "exhausted": True,
                "loops_completed": state.loops_completed,
                "max_loops": state.max_loops,
                "collected_parent_ids": state.collected_parent_ids,
                "parents_metadata": [p.metadata_summary() for p in state.parents],
                "message": (
                    "All top sub-chunks map to parents already collected. "
                    "Call finalize or try a different query."
                ),
            }

        parent_row = load_parent_chunk(winner.parent_id)
        if not parent_row:
            return {"error": f"Parent chunk {winner.parent_id} not found in Postgres"}

        progress.set(f"Analyzing parent chunk {winner.parent_id}", 100)

        loop_num = state.loops_completed + 1
        record = build_parent_record(
            parent_row=parent_row,
            loop=loop_num,
            loop_query=query,
            winning_sub_id=winner.sub_id,
            vector_score=winner.vector_score,
            rerank_score=winner.rerank_score,
        )

        state.parents.append(record)
        state.loops_completed = loop_num
        state.loop_history.append(
            {
                "loop": loop_num,
                "query": query,
                "parent_id": record.parent_id,
                "winning_sub_id": record.winning_sub_id,
                "label": record.label,
            }
        )
        save_state(session_id, state)

        prior_metadata = [p.metadata_summary() for p in state.parents[:-1]]

        progress.finish()
        finished = True

        return {
            "mode": "retrieve",
            "ticker": active_ticker,
            "loop": loop_num,
            "loop_query": query,
            "loops_completed": state.loops_completed,
            "max_loops": state.max_loops,
            "exhausted": False,
            "new_parent": record.to_dict(),
            "collected_parent_ids": state.collected_parent_ids,
            "parents_metadata": prior_metadata,
            "original_question": state.original_question,
            "message": (
                f"Loop {loop_num}: collected {record.label}. "
                "Read the parent chunk — if you need more detail or it cross-references "
                "another section, call retrieve again with a new query; otherwise finalize."
            ),
        }
    finally:
        if progress is not None and not finished:
            progress.abandon()


def finalize_loop(session_id: str, *, source: str = "mcp") -> dict[str, Any]:
    """Merge collected parents and clear state; show a short finalize chip.

    Use when: MCP query_rag mode=finalize.
    Logic: start Finalizing chip at 0 → merge context → 100 → delete.
    Returns: combined_context + citations for the host to answer.
    """
    progress: RagQueryFinalizeProgress | None = None
    finished = False
    try:
        progress = RagQueryFinalizeProgress.start(session_id, source=source)

        state = load_state(session_id)
        if state is None or not state.parents:
            clear_state(session_id)
            progress.finish(message="Done…")
            finished = True
            return {
                "mode": "finalize",
                "error": "No parent chunks collected. Run retrieve first or reset.",
                "parent_count": 0,
                "combined_context": "",
            }

        seen: set[str] = set()
        ordered: list[ParentChunkRecord] = []
        for parent in state.parents:
            if parent.parent_id in seen:
                continue
            seen.add(parent.parent_id)
            ordered.append(parent)

        parts: list[str] = []
        for parent in ordered:
            header = f"[{parent.label} | {parent.filing_key} | parent_id={parent.parent_id}]"
            parts.append(f"{header}\n{parent.content}")

        combined = FINALIZE_SEPARATOR.join(parts)
        original = state.original_question
        parent_count = len(ordered)
        citations = [_citation_dict(p) for p in ordered]

        clear_state(session_id)

        progress.finish(message="Done…")
        finished = True

        return {
            "mode": "finalize",
            "original_question": original,
            "ticker": state.ticker,
            "parent_count": parent_count,
            "combined_context": combined,
            "citations": citations,
            "parents_metadata": [p.metadata_summary() for p in ordered],
            "message": (
                f"Merged {parent_count} parent section(s). "
                "Answer the user using combined_context. "
                "End your reply with a Sources line — one short label per section from "
                "citations (e.g. 'Sources: NVDA · 10-K · FY2025 · section #7; ...'). "
                "Do not paste parent_id or chunk text."
            ),
        }
    finally:
        if progress is not None and not finished:
            progress.abandon()


def reset_loop(session_id: str) -> dict[str, Any]:
    clear_state(session_id)
    return {
        "mode": "reset",
        "message": "RAG query state cleared. Start a new retrieval run with retrieve.",
    }
