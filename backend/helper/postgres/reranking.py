"""Rerank provider abstraction — swap HF / OpenRouter via RERANK_PROVIDER."""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

_provider: RerankProvider | None = None


@runtime_checkable
class RerankProvider(Protocol):
    """Layman: scores how well each passage matches a query.

    Use when: query_rag retrieve reranks vector-search hits.
    Logic: provider-specific HTTP call → one float score per passage (same order).
    Returns: list[float] aligned with input texts.
    """

    @property
    def model_id(self) -> str: ...

    def score(
        self,
        query: str,
        texts: list[str],
        *,
        model_id: str | None = None,
        timeout_s: float = 120.0,
    ) -> list[float]: ...


def _provider_name() -> str:
    return os.getenv("RERANK_PROVIDER", "huggingface").strip().lower() or "huggingface"


def get_rerank_provider() -> RerankProvider:
    """Return the configured rerank provider (cached). Default: huggingface."""
    global _provider
    if _provider is not None:
        return _provider

    name = _provider_name()
    if name in ("hf", "huggingface"):
        from helper.postgres.hf_rerank import HuggingFaceRerankProvider

        _provider = HuggingFaceRerankProvider()
    elif name in ("openrouter", "openai"):
        from helper.postgres.openrouter_rerank import OpenRouterRerankProvider

        _provider = OpenRouterRerankProvider()
    else:
        raise ValueError(
            f"Unknown RERANK_PROVIDER={name!r}. Use 'huggingface' or 'openrouter'."
        )
    return _provider


def reset_rerank_provider() -> None:
    """Clear cached provider (tests / after env changes)."""
    global _provider
    _provider = None


def get_rerank_model() -> str:
    return get_rerank_provider().model_id
