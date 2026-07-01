"""Pure-Python cosine similarity for embed homework (no numpy)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"Vector length mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class ScoredItem:
    index: int
    score: float
    item: object


def rank_by_similarity(
    query_vector: list[float],
    chunk_vectors: list[list[float]],
    *,
    top_k: int = 3,
) -> list[tuple[int, float]]:
    """Return (index, score) pairs sorted by descending cosine similarity."""
    scored: list[tuple[int, float]] = []
    for i, vec in enumerate(chunk_vectors):
        scored.append((i, cosine_similarity(query_vector, vec)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
