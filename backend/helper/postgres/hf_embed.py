"""Hugging Face Inference API — feature-extraction embeddings for RAG."""

from __future__ import annotations

import os
from typing import Any

import httpx

from integrations.hf_client import HuggingFaceError, get_hf_token

DEFAULT_EMBED_MODEL = "BAAI/bge-base-en-v1.5"
EXPECTED_DIMENSION = 768
HF_INFERENCE_BASE = "https://router.huggingface.co/hf-inference/models"
EMBED_BATCH_SIZE = 32
EMBED_PARALLEL_BATCHES = 4


class HuggingFaceEmbedError(HuggingFaceError):
    pass


def get_embed_model() -> str:
    return os.getenv("HF_EMBED_MODEL", "").strip() or DEFAULT_EMBED_MODEL


def _feature_extraction_url(model_id: str) -> str:
    return f"{HF_INFERENCE_BASE}/{model_id}/pipeline/feature-extraction"


def _mean_pool(token_vectors: list[list[float]]) -> list[float]:
    if not token_vectors:
        return []
    dim = len(token_vectors[0])
    sums = [0.0] * dim
    for row in token_vectors:
        if len(row) != dim:
            raise HuggingFaceEmbedError(
                f"Inconsistent token vector dimensions: expected {dim}, got {len(row)}"
            )
        for i, val in enumerate(row):
            sums[i] += float(val)
    n = len(token_vectors)
    return [s / n for s in sums]


def _normalize_embedding(raw: Any) -> list[float]:
    """Convert HF feature-extraction response to a single sentence vector."""
    if not isinstance(raw, list) or not raw:
        raise HuggingFaceEmbedError(f"Unexpected embedding response type: {type(raw)}")

    if all(isinstance(x, (int, float)) for x in raw):
        return [float(x) for x in raw]

    if all(isinstance(x, list) for x in raw):
        token_rows = [[float(v) for v in row] for row in raw]
        return _mean_pool(token_rows)

    raise HuggingFaceEmbedError(f"Cannot parse embedding shape: {type(raw[0])}")


def _parse_embed_response(
    texts: list[str], data: Any, *, model: str
) -> list[list[float]]:
    if isinstance(data, dict) and "error" in data:
        raise HuggingFaceEmbedError(str(data["error"]))

    if len(texts) == 1:
        vectors = [_normalize_embedding(data)]
    else:
        if not isinstance(data, list) or len(data) != len(texts):
            raise HuggingFaceEmbedError(
                f"Expected {len(texts)} embeddings, got {type(data)} len="
                f"{len(data) if isinstance(data, list) else 'n/a'}"
            )
        vectors = [_normalize_embedding(item) for item in data]

    for i, vec in enumerate(vectors):
        if len(vec) != EXPECTED_DIMENSION:
            raise HuggingFaceEmbedError(
                f"Embedding {i} has dimension {len(vec)}, expected {EXPECTED_DIMENSION} "
                f"for model {model}"
            )

    return vectors


def _raise_for_embed_status(response: httpx.Response, *, model: str, url: str) -> None:
    if response.status_code == 429:
        raise HuggingFaceEmbedError(
            "HF rate limit (429). Wait and retry, or reduce batch size."
        )
    if response.status_code == 503:
        raise HuggingFaceEmbedError(
            f"Model {model} unavailable (503). Retry in a few seconds."
        )
    if response.status_code >= 400:
        detail = response.text[:300]
        raise HuggingFaceEmbedError(f"HF embed API {response.status_code}: {detail}")


def embed_texts(
    texts: list[str],
    *,
    model_id: str | None = None,
    timeout_s: float = 120.0,
) -> list[list[float]]:
    """
    Embed one or more texts via HF feature-extraction API.

    Returns one vector per input string. Default model: BAAI/bge-base-en-v1.5 (768 dims).
    """
    if not texts:
        return []

    model = model_id or get_embed_model()
    url = _feature_extraction_url(model)
    token = get_hf_token()
    payload = {"inputs": texts if len(texts) > 1 else texts[0], "normalize": True}

    try:
        with httpx.Client(timeout=timeout_s) as client:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
    except httpx.RequestError as exc:
        raise HuggingFaceEmbedError(
            f"Cannot reach Hugging Face embedding API at {url}. ({exc})"
        ) from exc

    _raise_for_embed_status(response, model=model, url=url)
    return _parse_embed_response(texts, response.json(), model=model)


async def embed_texts_async(
    texts: list[str],
    *,
    model_id: str | None = None,
    timeout_s: float = 120.0,
) -> list[list[float]]:
    """Async variant of embed_texts using httpx.AsyncClient."""
    if not texts:
        return []

    model = model_id or get_embed_model()
    url = _feature_extraction_url(model)
    token = get_hf_token()
    payload = {"inputs": texts if len(texts) > 1 else texts[0], "normalize": True}

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
    except httpx.RequestError as exc:
        raise HuggingFaceEmbedError(
            f"Cannot reach Hugging Face embedding API at {url}. ({exc})"
        ) from exc

    _raise_for_embed_status(response, model=model, url=url)
    return _parse_embed_response(texts, response.json(), model=model)


def vector_to_pg_literal(vec: list[float]) -> str:
    """Format a float list for Postgres pgvector cast."""
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"
