"""Embed sub-chunks in Postgres via the configured EmbedProvider."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from helper.postgres.db import get_database_url, schema_is_ready
from helper.postgres.embedding import (
    embed_texts,
    embed_texts_async,
    get_embed_batch_size,
    get_embed_model,
    get_embed_parallel_batches,
    vector_to_pg_literal,
)

logger = logging.getLogger(__name__)


@dataclass
class EmbedStats:
    document_id: str
    embedded_count: int
    model_id: str


def count_unembedded(document_id: str, *, database_url: str | None = None) -> int:
    url = database_url or get_database_url()
    if not url:
        return 0

    import psycopg

    doc_uuid = uuid.UUID(document_id)
    with psycopg.connect(url) as conn:
        if not schema_is_ready(conn):
            return 0
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM sub_chunks sc
                JOIN parent_chunks pc ON sc.parent_id = pc.id
                WHERE pc.document_id = %s AND sc.embedding IS NULL
                """,
                (doc_uuid,),
            )
            row = cur.fetchone()
            return int(row[0] or 0) if row else 0


def _load_unembedded_rows(document_id: str, url: str) -> list[tuple[str, str]]:
    import psycopg

    doc_uuid = uuid.UUID(document_id)
    with psycopg.connect(url) as conn:
        if not schema_is_ready(conn):
            raise RuntimeError(
                "RAG tables missing. Run: python -m helper.postgres.db migrate"
            )
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sc.id::text, sc.content
                FROM sub_chunks sc
                JOIN parent_chunks pc ON sc.parent_id = pc.id
                WHERE pc.document_id = %s AND sc.embedding IS NULL
                ORDER BY pc.chunk_index, sc.id
                """,
                (doc_uuid,),
            )
            return cur.fetchall()


def _apply_embed_batch(
    url: str,
    *,
    ids: list[str],
    vectors: list[list[float]],
    model_id: str,
    now: datetime,
) -> None:
    import psycopg

    with psycopg.connect(url) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                for sub_id, vec in zip(ids, vectors, strict=True):
                    cur.execute(
                        """
                        UPDATE sub_chunks
                        SET embedding = %s::vector,
                            embedded_at = %s,
                            embedding_model = %s
                        WHERE id = %s
                        """,
                        (
                            vector_to_pg_literal(vec),
                            now,
                            model_id,
                            uuid.UUID(sub_id),
                        ),
                    )


def embed_document(document_id: str, *, database_url: str | None = None) -> EmbedStats:
    url = database_url or get_database_url()
    if not url:
        raise ValueError("DATABASE_URL is required for embed_document")

    model_id = get_embed_model()
    rows = _load_unembedded_rows(document_id, url)

    if not rows:
        return EmbedStats(document_id=document_id, embedded_count=0, model_id=model_id)

    embedded_total = 0
    now = datetime.now(timezone.utc)
    batch_size = get_embed_batch_size()

    for batch_start in range(0, len(rows), batch_size):
        batch = rows[batch_start : batch_start + batch_size]
        ids = [r[0] for r in batch]
        texts = [r[1] for r in batch]
        vectors = embed_texts(texts, model_id=model_id)
        _apply_embed_batch(url, ids=ids, vectors=vectors, model_id=model_id, now=now)
        embedded_total += len(batch)

    logger.info(
        "postgres_embed: document_id=%s embedded=%s model=%s",
        document_id,
        embedded_total,
        model_id,
    )
    return EmbedStats(
        document_id=document_id,
        embedded_count=embedded_total,
        model_id=model_id,
    )


async def embed_document_async(
    document_id: str, *, database_url: str | None = None
) -> EmbedStats:
    """Embed unembedded sub-chunks with up to get_embed_parallel_batches() calls in flight."""
    url = database_url or get_database_url()
    if not url:
        raise ValueError("DATABASE_URL is required for embed_document_async")

    model_id = get_embed_model()
    rows = await asyncio.to_thread(_load_unembedded_rows, document_id, url)

    if not rows:
        return EmbedStats(document_id=document_id, embedded_count=0, model_id=model_id)

    batch_size = get_embed_batch_size()
    parallel = get_embed_parallel_batches()

    batches: list[tuple[list[str], list[str]]] = []
    for batch_start in range(0, len(rows), batch_size):
        batch = rows[batch_start : batch_start + batch_size]
        ids = [r[0] for r in batch]
        texts = [r[1] for r in batch]
        batches.append((ids, texts))

    embedded_total = 0
    now = datetime.now(timezone.utc)

    for group_start in range(0, len(batches), parallel):
        group = batches[group_start : group_start + parallel]
        vectors_groups = await asyncio.gather(
            *[embed_texts_async(texts, model_id=model_id) for _, texts in group]
        )
        for (ids, _), vectors in zip(group, vectors_groups, strict=True):
            await asyncio.to_thread(
                _apply_embed_batch,
                url,
                ids=ids,
                vectors=vectors,
                model_id=model_id,
                now=now,
            )
            embedded_total += len(ids)

    logger.info(
        "postgres_embed: document_id=%s embedded=%s model=%s (async)",
        document_id,
        embedded_total,
        model_id,
    )
    return EmbedStats(
        document_id=document_id,
        embedded_count=embedded_total,
        model_id=model_id,
    )
