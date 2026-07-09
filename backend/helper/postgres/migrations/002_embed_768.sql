-- RAG Phase 2: HF bge-base 768-dim embeddings (wipes stale rows on first apply)

TRUNCATE sub_chunks, parent_chunks, documents CASCADE;

ALTER TABLE sub_chunks
  ALTER COLUMN embedding TYPE vector(768) USING NULL;

ALTER TABLE sub_chunks
  ADD COLUMN IF NOT EXISTS embedded_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS embedding_model TEXT;

CREATE INDEX IF NOT EXISTS idx_sub_chunks_embedding
  ON sub_chunks USING hnsw (embedding vector_cosine_ops);
