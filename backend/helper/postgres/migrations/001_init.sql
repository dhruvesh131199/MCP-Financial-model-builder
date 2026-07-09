-- RAG: local Postgres / Aurora pgvector schema
-- Run once: psql "$DATABASE_URL" -f helper/postgres/migrations/001_init.sql

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
  document_id UUID PRIMARY KEY,
  ticker      TEXT NOT NULL,
  year        INT NOT NULL,
  doctype     TEXT NOT NULL,
  source      TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (ticker, year, doctype)
);

CREATE TABLE IF NOT EXISTS parent_chunks (
  id            TEXT PRIMARY KEY,
  document_id   UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
  ticker        TEXT NOT NULL,
  year          INT NOT NULL,
  doctype       TEXT NOT NULL,
  chunk_index   INT NOT NULL,
  content       TEXT NOT NULL,
  char_count    INT NOT NULL,
  approx_tokens INT NOT NULL,
  UNIQUE (ticker, year, doctype, chunk_index)
);

CREATE TABLE IF NOT EXISTS sub_chunks (
  id        UUID PRIMARY KEY,
  parent_id TEXT NOT NULL REFERENCES parent_chunks(id) ON DELETE CASCADE,
  content   TEXT NOT NULL,
  embedding vector(1536)
);

CREATE INDEX IF NOT EXISTS idx_parent_chunks_filing_order
  ON parent_chunks (ticker, year, doctype, chunk_index);

CREATE INDEX IF NOT EXISTS idx_sub_chunks_parent ON sub_chunks (parent_id);
