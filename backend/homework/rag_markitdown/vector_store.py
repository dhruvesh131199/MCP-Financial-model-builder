"""Vector store protocol — NoOp default, Postgres when DATABASE_URL is set."""

from __future__ import annotations

import logging
import os
from typing import Protocol

from homework.rag_markitdown.schema import IngestResult

logger = logging.getLogger(__name__)


class VectorStore(Protocol):
    def ingest(self, result: IngestResult) -> None: ...


class NoOpVectorStore:
    """Logs ingest metadata when Postgres is not configured."""

    def ingest(self, result: IngestResult) -> None:
        subchunks = result.chunk_plan.subchunk_count if result.chunk_plan else 0
        parents = result.chunk_plan.parent_count if result.chunk_plan else 0
        first_parent = (
            result.chunk_plan.parent_chunks[0].id
            if result.chunk_plan and result.chunk_plan.parent_chunks
            else None
        )
        logger.info(
            "vector_store noop: document_id=%s parents=%s first_parent=%s subchunks=%s",
            result.document_id,
            parents,
            first_parent,
            subchunks,
        )


def get_vector_store() -> VectorStore:
    """PostgresVectorStore if DATABASE_URL is set, else NoOp."""
    if os.environ.get("DATABASE_URL", "").strip():
        from homework.rag_markitdown.postgres_store import PostgresVectorStore

        return PostgresVectorStore()
    return NoOpVectorStore()
