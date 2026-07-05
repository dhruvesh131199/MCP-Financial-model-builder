# RAG homework Phase 1 — annual 10-K → MarkItDown

Learn the ingest path before merging into production and adding vector search.

## What this module does

1. **Fetch** the latest **primary 10-K** (full annual report: business, risks, MD&A, statements, footnotes)
2. **Convert** to markdown with [MarkItDown](https://github.com/microsoft/markitdown)
3. **Analyze** SEC Item sections → char counts and ~token estimates
4. **Chunk** each Item into parent + sub-chunks for RAG (`chunks.json`)
5. **Save** raw file + `converted.md` + `sections.json` + `chunks.json` + `report.html`

This is **not** the same as `fetch_report(just_financials)`, which stores structured XBRL tables for the Files panel.

Phase 2 (production): when `DATABASE_URL` is set, ingest **embeds sub-chunks** via Hugging Face (`BAAI/bge-base-en-v1.5`, 768-dim) into Postgres. Cache hits backfill any rows still missing embeddings. Vector search / `query_rag` MCP is not wired yet.

## Flow

```
MCP fetch_report(full_report) ──┐
                          ├──► pipeline.ingest_* ──► MarkItDown ──► converted.md
Homework API upload  ─────┘                              ├──► section_analyze ──► sections.json
CLI run.py --ticker ──────┘                              ├──► chunk_plan ──► chunks.json
                                                         └──► report.html (outline viewer)
```

Phase 2 (retrieval): `query_rag` MCP tool — host-driven loop retrieval (max 15), global pgvector top-10 + HF rerank. Requires `DATABASE_URL` + `HF_TOKEN`.

## Section outline

After MarkItDown, `section_analyze.py` scans `converted.md` for SEC **Item** headers (e.g. `Item 1A. Risk Factors`).

- **Preamble** — everything before the first Item (often huge on iXBRL HTML: XBRL tags, cover page)
- **Item rows** — one per SEC Item; char count = span until the next Item
- **~Tokens** — `round(char_count / 4)` (homework approximation, not a tokenizer)

**TOC dedup:** filings often list Items twice (table of contents + body). We keep the match with the **largest following span** — the body wins.

**Human preview:** open the **original** `raw_*.htm` / `raw_*.pdf` (browser or API `/documents/{id}/raw`), not the markdown dump.

**Citations:** use Item labels (e.g. "Item 1A — Risk Factors"), not page numbers.

## CLI

From `backend/` (with venv + `pip install -r requirements-homework-rag.txt`):

```bash
python -m homework.rag_markitdown.run --ticker AAPL --open
python -m homework.rag_markitdown.run --upload ./sample.pdf --upload-ticker AAPL --upload-year 2025
python -m homework.rag_markitdown.run --batch AAPL,WMT,COST,MSFT,JPM --summary-csv
```

Upload requires `--upload-ticker` and `--upload-year` (doctype defaults to `10K`).

Output: `homework/rag_markitdown/output/{TICKER}_{timestamp}/`

Batch mode writes `output/batch_{timestamp}/summary.csv` with columns: ticker, item_id, title, chars, tokens.

## Chunk plan (`chunks.json`)

Each **Item** (preamble skipped) is split into parent + sub-chunks. Parent IDs are deterministic and Aurora-ready:

| Level | ID / fields |
|-------|-------------|
| **Parent** | `id` = `{TICKER}_{YEAR}_{DOCTYPE}_P_{NN}` e.g. `AAPL_2025_10K_P_01` |
| | `ticker`, `year`, `doctype`, `chunk_index` (global 1-based order), `content`, `char_count`, `approx_tokens` |
| **Sub-chunk** | `id` = random UUID; `parent_id`, `content`, `embedding` (`null` at ingest) |

**Split rules:**

| Level | Rule |
|-------|------|
| Parent | 1 chunk if ≤ 12,000 chars; else `ceil(len/10_000)` splits, **500** char overlap |
| Sub-chunk | **1,000** chars, **200** overlap — future pgvector embed units |

**Year:** from SEC `period_of_report` (fallback `filing_date`). **Doctype:** `10-K` → `10K`.

**Neighbor lookup (RAG):** same `ticker/year/doctype` and `chunk_index ± 1`.

`meta.json` `chunk_plan` summary stores `ticker`, `year`, `doctype`, counts (no chunk text).

API: `GET /api/homework/rag/documents/{id}/chunks`

## Local Postgres + pgvector (optional)

When `DATABASE_URL` is set in `backend/.env`, ingest upserts into Postgres and **embeds** sub-chunks (768-dim HF). Requires `HF_TOKEN` in `backend/.env`.

**1. Create DB in Postico** (e.g. `fmb_rag`) and enable extension:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

**2. Run migration** (Postico SQL window, or CLI):

```bash
cd backend && source .venv/bin/activate
pip install -r requirements-homework-rag.txt
# Applies 001_init.sql then 002_embed_768.sql (002 truncates RAG tables — run once before deploy)
python -m homework.rag_markitdown.db migrate
```

**3. Configure** `backend/.env`:

```bash
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/fmb_rag
HF_TOKEN=hf_...
# optional:
HF_EMBED_MODEL=BAAI/bge-base-en-v1.5
```

**4. Ingest** via UI or API — parents + subs land in `parent_chunks` / `sub_chunks` with embeddings. Re-fetch same `ticker/year/doctype` replaces rows for that filing.

After migrating to 768-dim, **re-fetch** 10-Ks (`fetch_report(full_report)`) so Postgres repopulates with embedded chunks.

**Verify in Postico:**

```sql
SELECT id, chunk_index, char_count, approx_tokens
FROM parent_chunks WHERE ticker = 'AAPL' ORDER BY chunk_index LIMIT 5;

SELECT COUNT(*) FROM sub_chunks WHERE embedding IS NULL;
```

Without `DATABASE_URL`, behavior is unchanged (`chunks.json` only, noop vector store).

**Global dedup:** when Postgres has a row for `(ticker, year, doctype)`, fetch/upload **skips** re-download and MarkItDown — the session only gets a link in `rag_documents.json` (`from_cache: true`).

## Session dashboard integration

RAG lives in the main workspace sidebar (fourth section) — not a separate homework nav link.

| Surface | Path / behavior |
|---------|-----------------|
| Sidebar | **Upload financial document for your questions!** + RAG badge; one row per linked filing |
| Main panel | Fetch 10-K or upload; session document list with Done / error / “Loaded from library” |
| Chunk explorer | `/s/{sessionId}/rag/{documentId}/chunks` — parent/sub tree from session `chunks.json` or Postgres on cache hit |
| Session index | `data/sessions/{uuid}/rag_documents.json` |
| MCP | `fetch_report(full_report)` → `resolve_or_ingest_sec` (same dedup) |

**API (session-scoped):**

- `POST /api/sessions/{id}/rag/ingest/fetch` — `{ "ticker": "AAPL" }`
- `POST /api/sessions/{id}/rag/ingest/upload` — multipart: `file`, `ticker`, `year`, `doctype`
- `GET /api/sessions/{id}/rag/documents/{document_id}` — meta + URLs
- `GET /api/sessions/{id}/rag/documents/{document_id}/chunks` — full chunk plan

`GET /api/sessions/{id}` workspace payload includes `rag_documents[]`.

## Homework UI (dev only)

Session dashboard RAG hub (`RagHubPanel`) + `POST /api/sessions/{id}/rag/*` replace the old homework lab API and React page (removed).

## Narrative check

After convert, `meta.json` includes booleans for phrases like `risk factors` and `management` in the markdown — quick sanity check that narrative sections survived conversion.

## Merge criteria (later)

- Works for HTML and PDF tickers
- MCP and upload share `IngestResult`
- Item outline stable enough across your test tickers for chunk planning
- You can explain each step in the diagram above
