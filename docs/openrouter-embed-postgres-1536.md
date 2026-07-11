# Postgres: switch embedding column to 1536-dim (OpenRouter)

OpenRouter live smoke test (from this branch): `OpenRouterEmbedProvider` + `openai/text-embedding-3-small` returns **1 × 1536** vectors successfully.

## SQL to run yourself

Canonical file (same content):

[`backend/helper/postgres/migrations/003_embed_1536_openrouter.sql`](../backend/helper/postgres/migrations/003_embed_1536_openrouter.sql)

```sql
-- Wipes existing HF 768-dim vectors — re-ingest 10-Ks after this.

TRUNCATE sub_chunks, parent_chunks, documents CASCADE;

DROP INDEX IF EXISTS idx_sub_chunks_embedding;

ALTER TABLE sub_chunks
  ALTER COLUMN embedding TYPE vector(1536) USING NULL;

CREATE INDEX IF NOT EXISTS idx_sub_chunks_embedding
  ON sub_chunks USING hnsw (embedding vector_cosine_ops);
```

Not applied automatically by `python -m helper.postgres.db migrate` (that still only runs 001 + 002), so you control when data is wiped.

After running: restart MCP, re-fetch full 10-Ks, compare `.logs/rag_ingest_timing.log`.
