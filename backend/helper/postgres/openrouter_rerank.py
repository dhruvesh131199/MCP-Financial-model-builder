"""OpenRouter rerank provider for RAG (POST /api/v1/rerank)."""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_RERANK_MODEL = "cohere/rerank-v3.5"
OPENROUTER_RERANK_URL = "https://openrouter.ai/api/v1/rerank"


class OpenRouterRerankError(Exception):
    pass


def _get_api_key() -> str:
    token = (
        os.getenv("OPENROUTER_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )
    if not token:
        raise OpenRouterRerankError(
            "Missing OpenRouter API key. Set OPENROUTER_API_KEY in backend/.env"
        )
    return token


class OpenRouterRerankProvider:
    """Score (query, passage) pairs via OpenRouter `/api/v1/rerank`.

    Env:
      OPENROUTER_API_KEY=...
      OPENROUTER_RERANK_MODEL=cohere/rerank-v3.5
    """

    @property
    def model_id(self) -> str:
        return (
            os.getenv("OPENROUTER_RERANK_MODEL", "").strip() or DEFAULT_RERANK_MODEL
        )

    def score(
        self,
        query: str,
        texts: list[str],
        *,
        model_id: str | None = None,
        timeout_s: float = 120.0,
    ) -> list[float]:
        if not texts:
            return []

        model = model_id or self.model_id
        payload = {
            "model": model,
            "query": query,
            "documents": texts,
            "top_n": len(texts),
        }
        headers = {
            "Authorization": f"Bearer {_get_api_key()}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=timeout_s) as client:
                response = client.post(
                    OPENROUTER_RERANK_URL, headers=headers, json=payload
                )
        except httpx.RequestError as exc:
            raise OpenRouterRerankError(
                f"Cannot reach OpenRouter rerank API. ({exc})"
            ) from exc

        _raise_for_status(response)
        return _parse_rerank_scores(response.json(), len(texts))


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 429:
        raise OpenRouterRerankError(
            "OpenRouter rate limit (429). Wait and retry."
        )
    if response.status_code >= 400:
        detail = response.text[:400]
        raise OpenRouterRerankError(
            f"OpenRouter rerank API {response.status_code}: {detail}"
        )


def _parse_rerank_scores(data: Any, expected: int) -> list[float]:
    """Map OpenRouter results[{index, relevance_score}] to input-order floats."""
    if not isinstance(data, dict):
        raise OpenRouterRerankError(f"Unexpected response type: {type(data)}")
    if data.get("error"):
        raise OpenRouterRerankError(str(data["error"]))

    results = data.get("results")
    if not isinstance(results, list) or not results:
        raise OpenRouterRerankError("Empty or missing rerank results")

    scores: list[float | None] = [None] * expected
    for item in results:
        if not isinstance(item, dict):
            continue
        idx = item.get("index")
        score = item.get("relevance_score", item.get("score"))
        if idx is None or score is None:
            continue
        i = int(idx)
        if 0 <= i < expected:
            scores[i] = float(score)

    if any(s is None for s in scores):
        raise OpenRouterRerankError(
            f"Expected scores for {expected} documents, got incomplete results"
        )
    return [float(s) for s in scores]
