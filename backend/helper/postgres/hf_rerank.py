"""Hugging Face text-ranking reranker provider."""

from __future__ import annotations

import os
from typing import Any

import httpx

from integrations.hf_client import HuggingFaceError, get_hf_token

DEFAULT_RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
HF_INFERENCE_BASE = "https://router.huggingface.co/hf-inference/models"


class HuggingFaceRerankError(HuggingFaceError):
    pass


class HuggingFaceRerankProvider:
    """Score (query, passage) pairs via HF text-ranking pipeline."""

    @property
    def model_id(self) -> str:
        return os.getenv("HF_RERANK_MODEL", "").strip() or DEFAULT_RERANK_MODEL

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
        url = _text_ranking_url(model)
        token = get_hf_token()
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
            raise HuggingFaceRerankError(
                f"HF rerank API {response.status_code}: {detail}"
            )

        return _parse_rerank_scores(response.json(), len(texts))


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
