"""Postgres read helpers for filing dedup and chunk plan loading."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from helper.postgres.db import get_database_url, schema_is_ready
from helper.rag.schema import ChunkPlan, ParentChunk, SubChunk


@dataclass
class FilingLookup:
    document_id: str
    ticker: str
    year: int
    doctype: str
    source: str | None
    parent_count: int
    subchunk_count: int
    created_at: str | None


def lookup_filing(
    ticker: str,
    year: int,
    doctype: str,
    *,
    database_url: str | None = None,
) -> FilingLookup | None:
    url = database_url or get_database_url()
    if not url:
        return None

    import psycopg

    with psycopg.connect(url) as conn:
        if not schema_is_ready(conn):
            return None
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.document_id::text, d.ticker, d.year, d.doctype, d.source,
                       d.created_at::text,
                       (SELECT COUNT(*) FROM parent_chunks p
                        WHERE p.ticker = d.ticker AND p.year = d.year
                          AND p.doctype = d.doctype),
                       (SELECT COUNT(*) FROM sub_chunks s
                        JOIN parent_chunks p ON s.parent_id = p.id
                        WHERE p.ticker = d.ticker AND p.year = d.year
                          AND p.doctype = d.doctype)
                FROM documents d
                WHERE d.ticker = %s AND d.year = %s AND d.doctype = %s
                """,
                (ticker.strip().upper(), year, doctype.upper().replace("-", "")),
            )
            row = cur.fetchone()
    if not row:
        return None
    parent_count = int(row[6] or 0)
    if parent_count == 0:
        return None
    return FilingLookup(
        document_id=row[0],
        ticker=row[1],
        year=row[2],
        doctype=row[3],
        source=row[4],
        created_at=row[5],
        parent_count=parent_count,
        subchunk_count=int(row[7] or 0),
    )


def load_chunk_plan_from_db(
    document_id: str,
    *,
    database_url: str | None = None,
) -> ChunkPlan | None:
    url = database_url or get_database_url()
    if not url:
        return None

    import psycopg

    doc_uuid = uuid.UUID(document_id)
    with psycopg.connect(url) as conn:
        if not schema_is_ready(conn):
            return None
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ticker, year, doctype, source
                FROM documents WHERE document_id = %s
                """,
                (doc_uuid,),
            )
            doc_row = cur.fetchone()
            if not doc_row:
                return None
            ticker, year, doctype, _source = doc_row
            cur.execute(
                """
                SELECT id, ticker, year, doctype, chunk_index, content,
                       char_count, approx_tokens
                FROM parent_chunks
                WHERE document_id = %s
                ORDER BY chunk_index
                """,
                (doc_uuid,),
            )
            parent_rows = cur.fetchall()
            parents: list[ParentChunk] = []
            for prow in parent_rows:
                pid = prow[0]
                cur.execute(
                    """
                    SELECT id::text, content
                    FROM sub_chunks
                    WHERE parent_id = %s
                    ORDER BY id
                    """,
                    (pid,),
                )
                sub_rows = cur.fetchall()
                subchunks = [
                    SubChunk(
                        id=srow[0],
                        parent_id=pid,
                        content=srow[1],
                        embedding=None,
                    )
                    for srow in sub_rows
                ]
                parents.append(
                    ParentChunk(
                        id=pid,
                        ticker=prow[1],
                        year=prow[2],
                        doctype=prow[3],
                        chunk_index=prow[4],
                        content=prow[5],
                        char_count=prow[6],
                        approx_tokens=prow[7],
                        subchunks=subchunks,
                    )
                )
    subchunk_count = sum(len(p.subchunks) for p in parents)
    return ChunkPlan(
        document_id=document_id,
        ticker=ticker,
        year=year,
        doctype=doctype,
        config={},
        parent_chunks=parents,
        parent_count=len(parents),
        subchunk_count=subchunk_count,
        warnings=[],
    )


def filing_lookup_to_dict(lookup: FilingLookup) -> dict[str, Any]:
    return {
        "document_id": lookup.document_id,
        "ticker": lookup.ticker,
        "year": lookup.year,
        "doctype": lookup.doctype,
        "source": lookup.source,
        "parent_count": lookup.parent_count,
        "subchunk_count": lookup.subchunk_count,
        "created_at": lookup.created_at,
    }
