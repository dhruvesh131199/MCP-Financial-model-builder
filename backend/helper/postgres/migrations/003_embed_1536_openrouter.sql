-- Switch RAG embeddings to OpenAI text-embedding-3-small (1536-dim) via OpenRouter.
-- Run manually (or via migrate) AFTER setting EMBED_PROVIDER=openrouter.
-- Wipes existing HF 768-dim vectors — re-ingest 10-Ks after this.

TRUNCATE sub_chunks, parent_chunks, documents CASCADE;

DROP INDEX IF EXISTS idx_sub_chunks_embedding;

ALTER TABLE sub_chunks
  ALTER COLUMN embedding TYPE vector(1536) USING NULL;

CREATE INDEX IF NOT EXISTS idx_sub_chunks_embedding
  ON sub_chunks USING hnsw (embedding vector_cosine_ops);
