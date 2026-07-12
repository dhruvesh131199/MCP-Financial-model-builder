"""RAG rerank facade — RerankHit + score via RerankProvider, then rank hits."""

from __future__ import annotations

from dataclasses import dataclass

from helper.postgres.hf_rerank import HuggingFaceRerankError, _parse_rerank_scores
from helper.postgres.reranking import get_rerank_model, get_rerank_provider
from services.rag_vector_search import VectorHit

# Re-export for callers / tests that imported from this module.
__all__ = [
    "HuggingFaceRerankError",
    "RerankHit",
    "get_rerank_model",
    "rerank_hits",
    "_parse_rerank_scores",
]


@dataclass
class RerankHit:
    sub_id: str
    parent_id: str
    content: str
    chunk_index: int
    vector_score: float
    vector_rank: int
    rerank_score: float
    rerank_rank: int
    rank_delta: int
    document_id: str
    ticker: str
    year: int
    doctype: str
    document_source: str | None = None


def rerank_hits(
    query: str,
    hits: list[VectorHit],
    *,
    model_id: str | None = None,
    timeout_s: float = 120.0,
) -> list[RerankHit]:
    """Score vector hits with the configured rerank provider and return ranked hits.

    Use when: query_rag retrieve after semantic search.
    Logic: provider.score(query, texts) → sort by score desc → RerankHit list.
    Returns: e.g. [RerankHit(..., rerank_rank=1, rerank_score=0.95), ...]
    """
    if not hits:
        return []

    texts = [h.content for h in hits]
    scores = get_rerank_provider().score(
        query, texts, model_id=model_id, timeout_s=timeout_s
    )
    if len(scores) != len(hits):
        raise HuggingFaceRerankError(
            f"Expected {len(hits)} rerank scores, got {len(scores)}"
        )

    indexed = list(enumerate(scores))
    indexed.sort(key=lambda pair: pair[1], reverse=True)

    reranked: list[RerankHit] = []
    for rerank_rank, (orig_idx, score) in enumerate(indexed, start=1):
        hit = hits[orig_idx]
        reranked.append(
            RerankHit(
                sub_id=hit.sub_id,
                parent_id=hit.parent_id,
                content=hit.content,
                chunk_index=hit.chunk_index,
                vector_score=hit.vector_score,
                vector_rank=hit.vector_rank,
                rerank_score=score,
                rerank_rank=rerank_rank,
                rank_delta=hit.vector_rank - rerank_rank,
                document_id=hit.document_id,
                ticker=hit.ticker,
                year=hit.year,
                doctype=hit.doctype,
                document_source=hit.document_source,
            )
        )
    return reranked
