"""Embed sub-chunks in Postgres via Hugging Face."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from homework.rag_markitdown.db import get_database_url, schema_is_ready
from homework.rag_markitdown.hf_embed import (
    EMBED_BATCH_SIZE,
    embed_texts,
    get_embed_model,
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


def embed_document(
    document_id: str,
    *,
    database_url: str | None = None,
    on_step: Callable[[str], None] | None = None,
    filing_label: str | None = None,
) -> EmbedStats:
    url = database_url or get_database_url()
    if not url:
        raise ValueError("DATABASE_URL is required for embed_document")

    model_id = get_embed_model()
    doc_uuid = uuid.UUID(document_id)

    import psycopg

    with psycopg.connect(url) as conn:
        if not schema_is_ready(conn):
            raise RuntimeError(
                "RAG tables missing. Run: python -m homework.rag_markitdown.db migrate"
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
            rows = cur.fetchall()

        if not rows:
            return EmbedStats(document_id=document_id, embedded_count=0, model_id=model_id)

        embedded_total = 0
        now = datetime.now(timezone.utc)
        scope = filing_label or document_id
        if on_step:
            on_step(f"Embedding {scope} sub-chunks ({len(rows)} total)")

        for batch_start in range(0, len(rows), EMBED_BATCH_SIZE):
            batch = rows[batch_start : batch_start + EMBED_BATCH_SIZE]
            ids = [r[0] for r in batch]
            texts = [r[1] for r in batch]
            vectors = embed_texts(texts, model_id=model_id)

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
            embedded_total += len(batch)

        if on_step:
            on_step(f"Finished embedding {scope} ({embedded_total} sub-chunks)")

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
