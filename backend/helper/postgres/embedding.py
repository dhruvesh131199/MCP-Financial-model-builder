"""Embedding provider abstraction — swap HF / OpenRouter via EMBED_PROVIDER."""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

_provider: EmbedProvider | None = None


def _provider_name() -> str:
    return os.getenv("EMBED_PROVIDER", "huggingface").strip().lower() or "huggingface"


def get_embed_batch_size() -> int:
    """Texts per embed HTTP call. Env EMBED_BATCH_SIZE overrides; else 64 for openrouter, 32 for HF."""
    raw = os.getenv("EMBED_BATCH_SIZE", "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError as exc:
            raise ValueError(f"Invalid EMBED_BATCH_SIZE={raw!r}") from exc
    if _provider_name() in ("openrouter", "openai"):
        return 64
    return 32


def get_embed_parallel_batches() -> int:
    """Max concurrent embed batches on the async path. Env EMBED_PARALLEL_BATCHES overrides (default 4)."""
    raw = os.getenv("EMBED_PARALLEL_BATCHES", "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError as exc:
            raise ValueError(f"Invalid EMBED_PARALLEL_BATCHES={raw!r}") from exc
    return 4


# Backward-compatible module constants (HF defaults). Prefer get_embed_*() at runtime.
EMBED_BATCH_SIZE = 32
EMBED_PARALLEL_BATCHES = 4


@runtime_checkable
class EmbedProvider(Protocol):
    """Layman: turns text into vectors for RAG search.

    Use when: ingesting sub-chunks or embedding a query_rag query.
    Logic: provider-specific HTTP call → one float vector per input string.
    Returns: list of vectors, each length ``dimension``.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed_texts(
        self,
        texts: list[str],
        *,
        model_id: str | None = None,
        timeout_s: float = 120.0,
    ) -> list[list[float]]: ...

    async def embed_texts_async(
        self,
        texts: list[str],
        *,
        model_id: str | None = None,
        timeout_s: float = 120.0,
    ) -> list[list[float]]: ...


def get_embed_provider() -> EmbedProvider:
    """Return the configured embed provider (cached). Default: huggingface."""
    global _provider
    if _provider is not None:
        return _provider

    name = _provider_name()
    if name in ("hf", "huggingface"):
        from helper.postgres.hf_embed import HuggingFaceEmbedProvider

        _provider = HuggingFaceEmbedProvider()
    elif name in ("openrouter", "openai"):
        from helper.postgres.openrouter_embed import OpenRouterEmbedProvider

        _provider = OpenRouterEmbedProvider()
    else:
        raise ValueError(
            f"Unknown EMBED_PROVIDER={name!r}. Use 'huggingface' or 'openrouter'."
        )
    return _provider


def reset_embed_provider() -> None:
    """Clear cached provider (tests / after env changes)."""
    global _provider
    _provider = None


def get_embed_model() -> str:
    return get_embed_provider().model_id


def embed_texts(
    texts: list[str],
    *,
    model_id: str | None = None,
    timeout_s: float = 120.0,
) -> list[list[float]]:
    return get_embed_provider().embed_texts(
        texts, model_id=model_id, timeout_s=timeout_s
    )


async def embed_texts_async(
    texts: list[str],
    *,
    model_id: str | None = None,
    timeout_s: float = 120.0,
) -> list[list[float]]:
    return await get_embed_provider().embed_texts_async(
        texts, model_id=model_id, timeout_s=timeout_s
    )


def vector_to_pg_literal(vec: list[float]) -> str:
    """Format a float list for Postgres pgvector cast."""
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"
