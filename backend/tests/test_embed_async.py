"""Tests for async embedding batch parallelism."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from helper.postgres.embedding import get_embed_batch_size, get_embed_parallel_batches
from helper.postgres.hf_embed import EXPECTED_DIMENSION
from helper.postgres.postgres_embed import embed_document_async


def _fake_vector(seed: float = 0.1) -> list[float]:
    return [seed] * EXPECTED_DIMENSION


@patch("helper.postgres.postgres_embed._apply_embed_batch")
@patch("helper.postgres.postgres_embed.embed_texts_async", new_callable=AsyncMock)
@patch("helper.postgres.postgres_embed._load_unembedded_rows")
def test_embed_document_async_parallel_batches(
    mock_load, mock_embed_async, mock_apply, monkeypatch
):
    monkeypatch.delenv("EMBED_BATCH_SIZE", raising=False)
    monkeypatch.delenv("EMBED_PARALLEL_BATCHES", raising=False)
    monkeypatch.delenv("EMBED_PROVIDER", raising=False)

    batch_size = get_embed_batch_size()
    parallel = get_embed_parallel_batches()
    batch_count = parallel + 1
    row_count = batch_count * batch_size
    mock_load.return_value = [(f"id-{i}", f"text-{i}") for i in range(row_count)]

    async def _embed_side_effect(texts, **kwargs):
        return [_fake_vector(0.1) for _ in texts]

    mock_embed_async.side_effect = _embed_side_effect

    stats = asyncio.run(embed_document_async("doc-1", database_url="postgres://test"))

    assert stats.embedded_count == row_count
    assert mock_embed_async.call_count == batch_count
    assert mock_apply.call_count == batch_count

    first_group_calls = mock_embed_async.call_args_list[:parallel]
    assert len(first_group_calls) == parallel
    for call in first_group_calls:
        assert len(call.args[0]) == batch_size
