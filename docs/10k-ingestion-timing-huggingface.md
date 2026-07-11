# 10-K RAG ingest timing breakdown (Hugging Face embeddings)

Captured on branch `analyzing-time-for-ingesting-10k` during parallel `fetch_report(full_report)` for AAPL, COST, and WMT.

Embedder: Hugging Face (current production path via `embed_document_async`).

```
=== RAG ingest timing ===

AAPL FY2025  total=87.20s, subchunks: 335

  sec_fetch=9.83s

  markdown=1.18s

  chunking=0.04s  # includes section analyze

  db_upsert=1.46s

  embedding=71.15s

COST FY2025  total=86.66s, subchunks = 336

  sec_fetch=2.79s

  markdown=0.46s

  chunking=0.01s  # includes section analyze

  db_upsert=0.11s

  embedding=78.86s

WMT FY2026  total=111.06s, sub chunks = 111.06

  sec_fetch=5.65s

  markdown=1.11s

  chunking=0.05s  # includes section analyze

  db_upsert=0.86s

  embedding=97.97s
```

## Notes

- Steps align with ingest progress: SEC download → MarkItDown → chunking (incl. section analyze) → Postgres upsert → HF embed.
- Embedding dominates wall time (~80–90% of each filing).
- Filings ran in parallel; per-filing totals are wall clocks for that ticker×year, not additive across tickers.
