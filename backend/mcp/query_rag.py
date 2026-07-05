"""MCP handler for loop RAG retrieval."""

from __future__ import annotations

from typing import Any, Literal

from services.rag_loop_retrieval import finalize_loop, reset_loop, retrieve_loop

QueryRagMode = Literal["retrieve", "finalize", "reset"]


def run_query_rag(
    *,
    mode: QueryRagMode,
    session_id: str,
    query: str | None = None,
    ticker: str | None = None,
    original_question: str | None = None,
    top_k: int = 10,
) -> dict[str, Any]:
    if mode == "retrieve":
        return retrieve_loop(
            session_id,
            query or "",
            ticker=ticker,
            original_question=original_question,
            top_k=top_k,
        )
    if mode == "finalize":
        return finalize_loop(session_id)
    if mode == "reset":
        return reset_loop(session_id)
    return {"error": f"Invalid mode: {mode!r}. Use retrieve, finalize, or reset."}
