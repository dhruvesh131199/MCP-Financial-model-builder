"""Persist chunk plan to Postgres (pgvector) and embed sub-chunks via HF."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable

from homework.rag_markitdown.db import get_database_url, schema_is_ready
from homework.rag_markitdown.postgres_embed import embed_document
from homework.rag_markitdown.schema import IngestResult

logger = logging.getLogger(__name__)


class PostgresVectorStore:
    """Upsert documents + parent/sub chunks, then embed sub-chunks (768-dim HF)."""

    def __init__(self, database_url: str | None = None) -> None:
        self._url = database_url or get_database_url()
        if not self._url:
            raise ValueError("DATABASE_URL is required for PostgresVectorStore")

    def ingest(
        self,
        result: IngestResult,
        *,
        on_step: Callable[[str], None] | None = None,
    ) -> None:
        plan = result.chunk_plan
        if plan is None or not plan.parent_chunks:
            logger.info("postgres_store: skip empty chunk_plan document_id=%s", result.document_id)
            return

        label = f"{plan.ticker} FY{plan.year}"
        if on_step:
            on_step(f"Writing {label} chunks to database")

        import psycopg

        with psycopg.connect(self._url) as conn:
            if not schema_is_ready(conn):
                raise RuntimeError(
                    "RAG tables missing. Run: python -m homework.rag_markitdown.db migrate"
                )
            with conn.transaction():
                self._upsert_filing(conn, result)

        stats = embed_document(
            result.document_id,
            database_url=self._url,
            on_step=on_step,
            filing_label=label,
        )
        if on_step:
            on_step(f"Added {label} to database")
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
