"""OpenRouter OpenAI-compatible embeddings for RAG."""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_EMBED_MODEL = "openai/text-embedding-3-small"
DEFAULT_DIMENSION = 1536
OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"


class OpenRouterEmbedError(Exception):
    pass


def _get_api_key() -> str:
    token = (
        os.getenv("OPENROUTER_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )
    if not token:
        raise OpenRouterEmbedError(
            "Missing OpenRouter API key. Set OPENROUTER_API_KEY in backend/.env"
        )
    return token


class OpenRouterEmbedProvider:
    """Embed texts via OpenRouter `/api/v1/embeddings` (OpenAI-compatible).

    Env:
      OPENROUTER_API_KEY=...
      OPENROUTER_EMBED_MODEL=openai/text-embedding-3-small
      OPENROUTER_EMBED_DIMENSION=1536
    Postgres ``sub_chunks.embedding`` must be vector(N) matching ``dimension``.
    """

    @property
    def model_id(self) -> str:
        return os.getenv("OPENROUTER_EMBED_MODEL", "").strip() or DEFAULT_EMBED_MODEL

    @property
    def dimension(self) -> int:
        raw = os.getenv("OPENROUTER_EMBED_DIMENSION", "").strip()
        try:
            return int(raw) if raw else DEFAULT_DIMENSION
        except ValueError as exc:
            raise OpenRouterEmbedError(
                f"Invalid OPENROUTER_EMBED_DIMENSION={raw!r}"
            ) from exc

    def embed_texts(
        self,
        texts: list[str],
        *,
        model_id: str | None = None,
        timeout_s: float = 120.0,
    ) -> list[list[float]]:
        if not texts:
            return []
        model = model_id or self.model_id
        payload = {"model": model, "input": texts}
        headers = {
            "Authorization": f"Bearer {_get_api_key()}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=timeout_s) as client:
                response = client.post(
                    OPENROUTER_EMBEDDINGS_URL, headers=headers, json=payload
                )
        except httpx.RequestError as exc:
            raise OpenRouterEmbedError(
                f"Cannot reach OpenRouter embeddings API. ({exc})"
            ) from exc

        _raise_for_status(response)
        return _parse_response(texts, response.json(), dimension=self.dimension)

    async def embed_texts_async(
        self,
        texts: list[str],
        *,
        model_id: str | None = None,
        timeout_s: float = 120.0,
    ) -> list[list[float]]:
        if not texts:
            return []
        model = model_id or self.model_id
        payload = {"model": model, "input": texts}
        headers = {
            "Authorization": f"Bearer {_get_api_key()}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                response = await client.post(
                    OPENROUTER_EMBEDDINGS_URL, headers=headers, json=payload
                )
        except httpx.RequestError as exc:
            raise OpenRouterEmbedError(
                f"Cannot reach OpenRouter embeddings API. ({exc})"
            ) from exc

        _raise_for_status(response)
        return _parse_response(texts, response.json(), dimension=self.dimension)


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 429:
        raise OpenRouterEmbedError(
            "OpenRouter rate limit (429). Wait and retry, or reduce batch size."
        )
    if response.status_code >= 400:
        detail = response.text[:400]
        raise OpenRouterEmbedError(
            f"OpenRouter embed API {response.status_code}: {detail}"
        )


def _parse_response(
    texts: list[str], data: Any, *, dimension: int
) -> list[list[float]]:
    if not isinstance(data, dict):
        raise OpenRouterEmbedError(f"Unexpected response type: {type(data)}")
    if data.get("error"):
        raise OpenRouterEmbedError(str(data["error"]))

    items = data.get("data")
    if not isinstance(items, list) or len(items) != len(texts):
        raise OpenRouterEmbedError(
            f"Expected {len(texts)} embeddings, got "
            f"{len(items) if isinstance(items, list) else type(items)}"
        )

    # OpenAI-style responses may not preserve input order — sort by index.
    ordered = sorted(
        items,
        key=lambda item: int(item.get("index", 0))
        if isinstance(item, dict)
        else 0,
    )
    vectors: list[list[float]] = []
    for i, item in enumerate(ordered):
        if not isinstance(item, dict) or "embedding" not in item:
            raise OpenRouterEmbedError(f"Missing embedding at index {i}")
        raw = item["embedding"]
        if not isinstance(raw, list) or not raw:
            raise OpenRouterEmbedError(f"Bad embedding payload at index {i}")
        vec = [float(v) for v in raw]
        if len(vec) != dimension:
            raise OpenRouterEmbedError(
                f"Embedding {i} has dimension {len(vec)}, expected {dimension}. "
                "Match OPENROUTER_EMBED_DIMENSION to the model (and Postgres vector(N))."
            )
        vectors.append(vec)
    return vectors
