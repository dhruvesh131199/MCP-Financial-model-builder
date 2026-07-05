"""Hugging Face Inference API — text-ranking reranker for RAG retrieval."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from integrations.hf_client import HuggingFaceError, get_hf_token
from services.rag_vector_search import VectorHit

DEFAULT_RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
HF_INFERENCE_BASE = "https://router.huggingface.co/hf-inference/models"


class HuggingFaceRerankError(HuggingFaceError):
    pass


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


def get_rerank_model() -> str:
    return os.getenv("HF_RERANK_MODEL", "").strip() or DEFAULT_RERANK_MODEL


def _text_ranking_url(model_id: str) -> str:
    return f"{HF_INFERENCE_BASE}/{model_id}/pipeline/text-ranking"


def _parse_rerank_scores(data: Any, expected: int) -> list[float]:
    if isinstance(data, list):
        if not data:
            raise HuggingFaceRerankError("Empty rerank response")
        if all(isinstance(x, (int, float)) for x in data):
            if len(data) != expected:
                raise HuggingFaceRerankError(
                    f"Expected {expected} scores, got {len(data)}"
                )
            return [float(x) for x in data]
        if all(isinstance(x, dict) for x in data):
            scores: list[float | None] = [None] * expected
            for item in data:
                idx = item.get("index")
                score = item.get("score")
                if idx is None or score is None:
                    continue
                if 0 <= int(idx) < expected:
                    scores[int(idx)] = float(score)
            if any(s is None for s in scores):
                raise HuggingFaceRerankError("Rerank response missing index scores")
            return [float(s) for s in scores]
    if isinstance(data, dict):
        if "scores" in data and isinstance(data["scores"], list):
            return _parse_rerank_scores(data["scores"], expected)
        if "error" in data:
            raise HuggingFaceRerankError(str(data["error"]))
    raise HuggingFaceRerankError(f"Unexpected rerank response: {type(data)}")


def rerank_hits(
    query: str,
    hits: list[VectorHit],
    *,
    model_id: str | None = None,
    timeout_s: float = 120.0,
) -> list[RerankHit]:
    if not hits:
        return []

    model = model_id or get_rerank_model()
    url = _text_ranking_url(model)
    token = get_hf_token()
    texts = [h.content for h in hits]
    payload = {"inputs": {"query": query, "texts": texts}}

    try:
        with httpx.Client(timeout=timeout_s) as client:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
    except httpx.RequestError as exc:
        raise HuggingFaceRerankError(
            f"Cannot reach Hugging Face rerank API at {url}. ({exc})"
        ) from exc

    if response.status_code == 429:
        raise HuggingFaceRerankError("HF rate limit (429). Wait and retry.")
    if response.status_code == 503:
        raise HuggingFaceRerankError(
            f"Model {model} unavailable (503). Retry in a few seconds."
        )
    if response.status_code >= 400:
        detail = response.text[:300]
        raise HuggingFaceRerankError(f"HF rerank API {response.status_code}: {detail}")

    scores = _parse_rerank_scores(response.json(), len(hits))
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
