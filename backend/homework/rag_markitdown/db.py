"""Postgres connection and schema migration for homework RAG."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
INIT_SQL = MIGRATIONS_DIR / "001_init.sql"
_env_loaded = False


def _ensure_env_loaded() -> None:
    global _env_loaded
    if not _env_loaded:
        load_dotenv(_BACKEND_ROOT / ".env")
        _env_loaded = True


def get_database_url() -> str | None:
    _ensure_env_loaded()
    url = os.environ.get("DATABASE_URL", "").strip()
    return url or None


def schema_is_ready(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'parent_chunks'
            """
        )
        return cur.fetchone() is not None


def run_migrations(database_url: str | None = None) -> None:
    """Apply 001_init.sql (idempotent)."""
    import psycopg

    url = database_url or get_database_url()
    if not url:
        raise SystemExit("DATABASE_URL is not set")

    sql = INIT_SQL.read_text(encoding="utf-8")
    with psycopg.connect(url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)
        if schema_is_ready(conn):
            print(f"Schema ready ({INIT_SQL.name})")
        else:
            raise SystemExit("Migration ran but parent_chunks table not found")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args and args[0] not in {"migrate", "check"}:
        print("Usage: python -m homework.rag_markitdown.db migrate", file=sys.stderr)
        return 1
    cmd = args[0] if args else "migrate"
    if cmd == "migrate":
        run_migrations()
        return 0
    if cmd == "check":
        import psycopg

        url = get_database_url()
        if not url:
            print("DATABASE_URL not set")
            return 1
        with psycopg.connect(url) as conn:
            ok = schema_is_ready(conn)
        print("schema ready" if ok else "schema missing — run migrate")
        return 0 if ok else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
