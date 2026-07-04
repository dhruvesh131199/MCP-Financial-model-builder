"""
RAG retrieve homework CLI — pgvector top-K + HF rerank.

Run from backend/:
    python -m homework.rag_markitdown.retrieve_homework.run_retrieve_test \\
      --query "What are NVIDIA's principal risk factors?" \\
      --ticker NVDA --open
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from homework.rag_markitdown.hf_embed import (  # noqa: E402
    HuggingFaceEmbedError,
    embed_texts,
    get_embed_model,
)
from homework.rag_markitdown.hf_rerank import (  # noqa: E402
    HuggingFaceRerankError,
    get_rerank_model,
    rerank_hits,
)
from homework.rag_markitdown.postgres_search import (  # noqa: E402
    resolve_latest_filing_year,
    search_sub_chunks,
)
from homework.rag_markitdown.retrieve_homework.report import (  # noqa: E402
    RetrieveTestReport,
    now_iso,
    preview_text,
    write_report,
)
from homework.rag_markitdown.storage import OUTPUT_ROOT  # noqa: E402


def run_retrieve_test(
    *,
    query: str,
    ticker: str = "NVDA",
    year: int | None = None,
    doctype: str = "10K",
    limit: int = 25,
    open_browser: bool = False,
) -> None:
    sym = ticker.strip().upper()
    doc_type = doctype.upper().replace("-", "")
    resolved_year = year
    if resolved_year is None:
        resolved_year = resolve_latest_filing_year(sym, doctype=doc_type)
    if resolved_year is None:
        raise ValueError(f"No {doc_type} filing in Postgres for {sym}")

    embed_model = get_embed_model()
    rerank_model = get_rerank_model()

    print(f"Query: {query}")
    print(f"Filing: {sym} {doc_type} FY{resolved_year}")
    print(f"Embed: {embed_model} · Rerank: {rerank_model}")

    query_vector = embed_texts([query], model_id=embed_model)[0]
    vector_hits = search_sub_chunks(
        query_vector,
        ticker=sym,
        year=resolved_year,
        doctype=doc_type,
        limit=limit,
    )
    if not vector_hits:
        raise ValueError("No embedded sub-chunks found for this filing")

    print(f"\nStage 1 — vector top {len(vector_hits)}:")
    for hit in vector_hits[:5]:
        print(
            f"  #{hit.vector_rank:2d}  {hit.vector_score:.4f}  "
            f"{hit.parent_id}  {preview_text(hit.content, 60)}"
        )
    if len(vector_hits) > 5:
        print(f"  … and {len(vector_hits) - 5} more")

    reranked = rerank_hits(query, vector_hits, model_id=rerank_model)

    print(f"\nStage 2 — after rerank:")
    for hit in reranked[:5]:
        delta = f"+{hit.rank_delta}" if hit.rank_delta > 0 else str(hit.rank_delta)
        print(
            f"  #{hit.rerank_rank:2d}  {hit.rerank_score:.4f}  "
            f"(was #{hit.vector_rank}, Δ{delta})  {preview_text(hit.content, 50)}"
        )
    if len(reranked) > 5:
        print(f"  … and {len(reranked) - 5} more")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = OUTPUT_ROOT / f"retrieve_test_{stamp}"
    report = RetrieveTestReport(
        query=query,
        embed_model=embed_model,
        rerank_model=rerank_model,
        ticker=sym,
        year=resolved_year,
        doctype=doc_type,
        vector_limit=limit,
        vector_hit_count=len(vector_hits),
        created_at=now_iso(),
        vector_hits=vector_hits,
        reranked_hits=reranked,
    )
    json_path = write_report(out_dir, report)
    html_path = out_dir / "retrieve_test_report.html"
    print(f"\nJSON: {json_path}")
    print(f"HTML: {html_path}")
    if open_browser:
        webbrowser.open(html_path.resolve().as_uri())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Homework: pgvector retrieve + HF rerank visualization"
    )
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--ticker", default="NVDA", help="Ticker filter (default NVDA)")
    parser.add_argument("--year", type=int, default=None, help="Fiscal year (default: latest in DB)")
    parser.add_argument("--doctype", default="10K", help="Document type (default 10K)")
    parser.add_argument("--limit", type=int, default=25, help="Vector retrieval limit (default 25)")
    parser.add_argument("--open", action="store_true", help="Open HTML report in browser")
    args = parser.parse_args(argv)

    try:
        run_retrieve_test(
            query=args.query,
            ticker=args.ticker,
            year=args.year,
            doctype=args.doctype,
            limit=args.limit,
            open_browser=args.open,
        )
    except (HuggingFaceEmbedError, HuggingFaceRerankError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
