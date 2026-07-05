"""Postgres pgvector search for RAG sub-chunks (global corpus)."""

from __future__ import annotations

from dataclasses import dataclass

from homework.rag_markitdown.db import get_database_url, schema_is_ready
from homework.rag_markitdown.hf_embed import vector_to_pg_literal

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


@dataclass
class VectorHit:
    sub_id: str
    parent_id: str
    content: str
    chunk_index: int
    vector_score: float
    vector_rank: int
    document_id: str
    ticker: str
    year: int
    doctype: str
    document_source: str | None = None


def _require_psycopg():
    if psycopg is None:
        raise ImportError(
            "psycopg is required for vector search. "
            "pip install -r requirements-homework-rag.txt"
        )
    return psycopg


def search_sub_chunks_global(
    query_vector: list[float],
    *,
    limit: int = 10,
    ticker: str | None = None,
    exclude_parent_ids: list[str] | None = None,
    database_url: str | None = None,
) -> list[VectorHit]:
    """Vector search across embedded sub-chunks; optionally filter by ticker."""
    url = database_url or get_database_url()
    if not url:
        raise ValueError("DATABASE_URL is required for vector search")

    pg = _require_psycopg()
    exclude = [pid for pid in (exclude_parent_ids or []) if pid]
    vec_literal = vector_to_pg_literal(query_vector)

    filter_sql = ""
    params: list[object] = [vec_literal]

    if ticker and ticker.strip():
        filter_sql += " AND pc.ticker = %s"
        params.append(ticker.strip().upper())

    if exclude:
        placeholders = ", ".join(["%s"] * len(exclude))
        filter_sql += f" AND pc.id NOT IN ({placeholders})"
        params.extend(exclude)

    params.extend([vec_literal, limit])

    with pg.connect(url) as conn:
        if not schema_is_ready(conn):
            raise RuntimeError(
                "RAG tables missing. Run: python -m homework.rag_markitdown.db migrate"
            )
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT sc.id::text, sc.parent_id, sc.content, pc.chunk_index,
                       d.document_id::text, d.ticker, d.year, d.doctype, d.source,
                       1 - (sc.embedding <=> %s::vector) AS score
                FROM sub_chunks sc
                JOIN parent_chunks pc ON sc.parent_id = pc.id
                JOIN documents d ON pc.document_id = d.document_id
                WHERE sc.embedding IS NOT NULL
                {filter_sql}
                ORDER BY sc.embedding <=> %s::vector
                LIMIT %s
                """,
                params,
            )
            rows = cur.fetchall()

    hits: list[VectorHit] = []
    for rank, row in enumerate(rows, start=1):
        hits.append(
            VectorHit(
                sub_id=row[0],
                parent_id=row[1],
                content=row[2],
                chunk_index=int(row[3]),
                document_id=row[4],
                ticker=row[5],
                year=int(row[6]),
                doctype=row[7],
                document_source=row[8],
                vector_score=float(row[9]),
                vector_rank=rank,
            )
        )
    return hits


def load_parent_chunk(
    parent_id: str,
    *,
    database_url: str | None = None,
) -> dict[str, object] | None:
    """Load full parent chunk row with document metadata."""
    url = database_url or get_database_url()
    if not url:
        raise ValueError("DATABASE_URL is required")

    pg = _require_psycopg()
    with pg.connect(url) as conn:
        if not schema_is_ready(conn):
            raise RuntimeError("RAG tables missing")
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pc.id, pc.document_id::text, pc.ticker, pc.year, pc.doctype,
                       pc.chunk_index, pc.content, pc.char_count, pc.approx_tokens,
                       d.source
                FROM parent_chunks pc
                JOIN documents d ON pc.document_id = d.document_id
                WHERE pc.id = %s
                """,
                (parent_id,),
            )
            row = cur.fetchone()

    if not row:
        return None

    return {
        "parent_id": row[0],
        "document_id": row[1],
        "ticker": row[2],
        "year": int(row[3]),
        "doctype": row[4],
        "chunk_index": int(row[5]),
        "content": row[6],
        "char_count": int(row[7]),
        "approx_tokens": int(row[8]),
        "document_source": row[9],
    }
