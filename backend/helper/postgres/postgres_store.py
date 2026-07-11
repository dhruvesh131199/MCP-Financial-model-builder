"""Persist chunk plan to Postgres (pgvector) and embed sub-chunks via HF."""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import nullcontext

from helper.postgres.db import get_database_url, schema_is_ready
from helper.postgres.postgres_embed import embed_document, embed_document_async
from helper.rag.schema import IngestResult

logger = logging.getLogger(__name__)


class PostgresVectorStore:
    """Upsert documents + parent/sub chunks, then embed sub-chunks via EmbedProvider."""

    def __init__(self, database_url: str | None = None) -> None:
        self._url = database_url or get_database_url()
        if not self._url:
            raise ValueError("DATABASE_URL is required for PostgresVectorStore")

    def ingest(
        self,
        result: IngestResult,
        *,
        progress=None,
        progress_label: str = "",
        timing=None,
        timing_key: str = "",
    ) -> None:
        plan = result.chunk_plan
        if plan is None or not plan.parent_chunks:
            logger.info("postgres_store: skip empty chunk_plan document_id=%s", result.document_id)
            if progress:
                progress.report(
                    f"{progress_label}: chunks uploaded", advance_steps=1
                )
                progress.report(
                    f"{progress_label}: embedding done", advance_steps=1
                )
            return

        label = progress_label or f"{plan.ticker} {plan.year}"
        if progress:
            progress.report(f"{label}: uploading chunks")
        with timing.step(timing_key, "db_upsert") if timing and timing_key else nullcontext():
            self.upsert_chunks(result)
        if progress:
            progress.report(f"{label}: chunks uploaded", advance_steps=1)
            progress.report(f"{label}: embedding")
        with timing.step(timing_key, "embedding") if timing and timing_key else nullcontext():
            stats = embed_document(result.document_id, database_url=self._url)
        if progress:
            progress.report(f"{label}: embedding done", advance_steps=1)
        logger.info(
            "postgres_store: document_id=%s %s_%s_%s parents=%s subchunks=%s embedded=%s",
            result.document_id,
            plan.ticker,
            plan.year,
            plan.doctype,
            plan.parent_count,
            plan.subchunk_count,
            stats.embedded_count,
        )

    async def ingest_async(
        self,
        result: IngestResult,
        *,
        progress=None,
        progress_label: str = "",
        timing=None,
        timing_key: str = "",
    ) -> None:
        plan = result.chunk_plan
        if plan is None or not plan.parent_chunks:
            logger.info(
                "postgres_store: skip empty chunk_plan document_id=%s", result.document_id
            )
            if progress:
                progress.report(
                    f"{progress_label}: chunks uploaded", advance_steps=1
                )
                progress.report(
                    f"{progress_label}: embedding done", advance_steps=1
                )
            return

        label = progress_label or f"{plan.ticker} {plan.year}"
        if progress:
            progress.report(f"{label}: uploading chunks")
        with timing.step(timing_key, "db_upsert") if timing and timing_key else nullcontext():
            await asyncio.to_thread(self.upsert_chunks, result)
        if progress:
            progress.report(f"{label}: chunks uploaded", advance_steps=1)
            progress.report(f"{label}: embedding")
        with timing.step(timing_key, "embedding") if timing and timing_key else nullcontext():
            stats = await embed_document_async(result.document_id, database_url=self._url)
        if progress:
            progress.report(f"{label}: embedding done", advance_steps=1)
        logger.info(
            "postgres_store: document_id=%s %s_%s_%s parents=%s subchunks=%s embedded=%s (async)",
            result.document_id,
            plan.ticker,
            plan.year,
            plan.doctype,
            plan.parent_count,
            plan.subchunk_count,
            stats.embedded_count,
        )

    def upsert_chunks(self, result: IngestResult) -> None:
        import psycopg

        with psycopg.connect(self._url) as conn:
            if not schema_is_ready(conn):
                raise RuntimeError(
                    "RAG tables missing. Run: python -m helper.postgres.db migrate"
                )
            with conn.transaction():
                self._upsert_filing(conn, result)

    def _upsert_filing(self, conn, result: IngestResult) -> None:
        plan = result.chunk_plan
        assert plan is not None

        with conn.cursor() as cur:
            # Delete chunks first so documents.document_id can be updated on re-ingest.
            cur.execute(
                """
                DELETE FROM parent_chunks
                WHERE ticker = %s AND year = %s AND doctype = %s
                """,
                (plan.ticker, plan.year, plan.doctype),
            )
            cur.execute(
                """
                INSERT INTO documents (document_id, ticker, year, doctype, source)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (ticker, year, doctype) DO UPDATE SET
                  document_id = EXCLUDED.document_id,
                  source = EXCLUDED.source
                """,
                (
                    uuid.UUID(result.document_id),
                    plan.ticker,
                    plan.year,
                    plan.doctype,
                    result.source.value,
                ),
            )
            for parent in plan.parent_chunks:
                cur.execute(
                    """
                    INSERT INTO parent_chunks (
                      id, document_id, ticker, year, doctype, chunk_index,
                      content, char_count, approx_tokens
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        parent.id,
                        uuid.UUID(result.document_id),
                        parent.ticker,
                        parent.year,
                        parent.doctype,
                        parent.chunk_index,
                        parent.content,
                        parent.char_count,
                        parent.approx_tokens,
                    ),
                )
                for sub in parent.subchunks:
                    cur.execute(
                        """
                        INSERT INTO sub_chunks (id, parent_id, content, embedding)
                        VALUES (%s, %s, %s, NULL)
                        """,
                        (uuid.UUID(sub.id), parent.id, sub.content),
                    )
