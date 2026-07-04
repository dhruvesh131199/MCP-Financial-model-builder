"""Postgres pgvector search for RAG sub-chunks."""

from __future__ import annotations

from dataclasses import dataclass

from homework.rag_markitdown.db import get_database_url, schema_is_ready
from homework.rag_markitdown.hf_embed import vector_to_pg_literal

try:
    import psycopg
except ImportError:  # pragma: no cover - optional via requirements-homework-rag.txt
    psycopg = None


@dataclass
class VectorHit:
    sub_id: str
    parent_id: str
    content: str
    chunk_index: int
    vector_score: float
    vector_rank: int


def _require_psycopg():
    if psycopg is None:
        raise ImportError(
            "psycopg is required for vector search. "
            "pip install -r requirements-homework-rag.txt"
        )
    return psycopg


def resolve_latest_filing_year(
    ticker: str,
    *,
    doctype: str = "10K",
    database_url: str | None = None,
) -> int | None:
    url = database_url or get_database_url()
    if not url:
        return None

    pg = _require_psycopg()
    sym = ticker.strip().upper()
    doc_type = doctype.upper().replace("-", "")
    with pg.connect(url) as conn:
        if not schema_is_ready(conn):
            return None
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT MAX(year)
                FROM documents
                WHERE ticker = %s AND doctype = %s
                """,
                (sym, doc_type),
            )
            row = cur.fetchone()
    if not row or row[0] is None:
        return None
    return int(row[0])


def search_sub_chunks(
    query_vector: list[float],
    *,
    ticker: str,
    year: int | None = None,
    doctype: str = "10K",
    limit: int = 25,
    database_url: str | None = None,
) -> list[VectorHit]:
    url = database_url or get_database_url()
    if not url:
        raise ValueError("DATABASE_URL is required for vector search")

    pg = _require_psycopg()
    sym = ticker.strip().upper()
    doc_type = doctype.upper().replace("-", "")
    resolved_year = year
    if resolved_year is None:
        resolved_year = resolve_latest_filing_year(sym, doctype=doc_type, database_url=url)
    if resolved_year is None:
        raise ValueError(f"No {doc_type} filing found in Postgres for ticker {sym}")

    vec_literal = vector_to_pg_literal(query_vector)
    with pg.connect(url) as conn:
        if not schema_is_ready(conn):
            raise RuntimeError(
                "RAG tables missing. Run: python -m homework.rag_markitdown.db migrate"
            )
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sc.id::text, sc.parent_id, sc.content, pc.chunk_index,
                       1 - (sc.embedding <=> %s::vector) AS score
                FROM sub_chunks sc
                JOIN parent_chunks pc ON sc.parent_id = pc.id
                WHERE pc.ticker = %s AND pc.year = %s AND pc.doctype = %s
                  AND sc.embedding IS NOT NULL
                ORDER BY sc.embedding <=> %s::vector
                LIMIT %s
                """,
                (vec_literal, sym, resolved_year, doc_type, vec_literal, limit),
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
                vector_score=float(row[4]),
                vector_rank=rank,
            )
        )
    return hits
