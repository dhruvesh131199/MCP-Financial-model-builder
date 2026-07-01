"""
RAG embed homework CLI — HF embeddings + cosine retrieval on 5–10 sub-chunks.

Run from backend/:
    python -m homework.rag_markitdown.embed_homework.run_embed_test \\
      --limit 8 --query "What are the company's risk factors?"
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from homework.rag_markitdown.chunk_ids import DocumentFilingKey  # noqa: E402
from homework.rag_markitdown.chunk_plan import build_chunk_plan  # noqa: E402
from homework.rag_markitdown.embed_homework.hf_embed_client import (  # noqa: E402
    EXPECTED_DIMENSION,
    HuggingFaceEmbedError,
    embed_texts,
    get_embed_model,
)
from homework.rag_markitdown.embed_homework.report import (  # noqa: E402
    ChunkHit,
    EmbedTestReport,
    now_iso,
    preview_text,
    write_report,
)
from homework.rag_markitdown.embed_homework.similarity import rank_by_similarity  # noqa: E402
from homework.rag_markitdown.schema import ChunkPlan  # noqa: E402
from homework.rag_markitdown.section_analyze import analyze_sections  # noqa: E402
from homework.rag_markitdown.storage import OUTPUT_ROOT  # noqa: E402

FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "tests"
    / "fixtures"
    / "sample_10k_items.md"
)


@dataclass
class SubChunkRow:
    sub_id: str
    parent_id: str
    item_label: str | None
    content: str


def resolve_chunks_path(
    chunks: str | None = None,
    *,
    ticker: str | None = None,
) -> Path | None:
    """
    Resolve chunks.json for embed test.

    - --ticker AAPL → newest OUTPUT_ROOT/AAPL_*/chunks.json
    - --chunks path/to/chunks.json → exact file
    - --chunks 'output/AAPL_*/chunks.json' → glob (quote so shell does not expand)
    """
    if ticker:
        sym = ticker.strip().upper()
        matches = sorted(
            OUTPUT_ROOT.glob(f"{sym}_*/chunks.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not matches:
            raise ValueError(
                f"No chunks.json for {sym} under {OUTPUT_ROOT}. "
                f"Run: python -m homework.rag_markitdown.run --ticker {sym}"
            )
        if len(matches) > 1:
            print(f"Note: using latest ingest ({matches[0].parent.name})")
        return matches[0]

    if not chunks:
        return None

    path = Path(chunks)
    if path.is_file():
        return path

    if "*" in chunks or "?" in chunks:
        matches = _glob_chunks_json(chunks)
        if not matches:
            raise ValueError(f"No chunks.json matches pattern: {chunks!r}")
        if len(matches) > 1:
            print(f"Note: using latest of {len(matches)} matches ({matches[0]})")
        return matches[0]

    if path.exists():
        return path

    raise ValueError(f"chunks path not found: {chunks}")


def _glob_chunks_json(pattern: str) -> list[Path]:
    """Glob chunks.json from cwd, pattern as-is, and OUTPUT_ROOT."""
    seen: set[Path] = set()
    matches: list[Path] = []

    def add(results: list[Path]) -> None:
        for p in results:
            resolved = p.resolve()
            if resolved.is_file() and resolved not in seen:
                seen.add(resolved)
                matches.append(resolved)

    add(list(Path.cwd().glob(pattern)))

    # e.g. homework/rag_markitdown/output/AAPL_*/chunks.json → under OUTPUT_ROOT
    marker = "rag_markitdown/output/"
    if marker in pattern:
        suffix = pattern.split(marker, 1)[1]
        add(list(OUTPUT_ROOT.glob(suffix)))
    elif not Path(pattern).is_absolute():
        add(list(OUTPUT_ROOT.glob(pattern)))

    return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)


def load_subchunks_from_fixture() -> tuple[list[SubChunkRow], str]:
    markdown = FIXTURE_PATH.read_text(encoding="utf-8")
    outline = analyze_sections(markdown)
    filing_key = DocumentFilingKey(ticker="DEMO", year=2025, doctype="10K")
    plan = build_chunk_plan(
        markdown, outline, "00000000-0000-0000-0000-000000000001", filing_key
    )
    return _flatten_plan(plan), f"fixture:{FIXTURE_PATH.name}"


def load_subchunks_from_chunks_json(path: Path) -> tuple[list[SubChunkRow], str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    plan = ChunkPlan.model_validate(data)
    return _flatten_plan(plan), f"chunks:{path}"


def _flatten_plan(plan: ChunkPlan) -> list[SubChunkRow]:
    rows: list[SubChunkRow] = []
    for parent in plan.parent_chunks:
        label = parent.item_label
        for sub in parent.subchunks:
            rows.append(
                SubChunkRow(
                    sub_id=sub.id,
                    parent_id=parent.id,
                    item_label=label,
                    content=sub.content,
                )
            )
    return rows


def print_top_hits(
    rows: list[SubChunkRow],
    ranked: list[tuple[int, float]],
) -> None:
    print("\nTop matches:")
    print(f"{'Rank':<5} {'Score':<8} {'Parent':<22} {'Item':<30} Preview")
    print("-" * 100)
    for rank, (idx, score) in enumerate(ranked, start=1):
        row = rows[idx]
        item = (row.item_label or "—")[:28]
        preview = preview_text(row.content, 50)
        print(
            f"{rank:<5} {score:<8.4f} {row.parent_id:<22} {item:<30} {preview}"
        )


def run_embed_test(
    *,
    query: str,
    limit: int = 8,
    chunks_path: Path | None = None,
    top_k: int = 3,
    open_browser: bool = False,
) -> Path:
    if chunks_path:
        rows, source = load_subchunks_from_chunks_json(chunks_path)
    else:
        rows, source = load_subchunks_from_fixture()

    if not rows:
        raise ValueError("No sub-chunks found in source")

    rows = rows[:limit]
    model_id = get_embed_model()

    print(f"Model: {model_id} (expected {EXPECTED_DIMENSION} dims)")
    print(f"Source: {source}")
    print(f"Embedding {len(rows)} sub-chunk(s)...")

    texts = [r.content for r in rows]
    chunk_vectors = embed_texts(texts, model_id=model_id)
    query_vector = embed_texts([query], model_id=model_id)[0]

    ranked = rank_by_similarity(query_vector, chunk_vectors, top_k=top_k)
    print_top_hits(rows, ranked)

    hits = [
        ChunkHit(
            sub_id=rows[idx].sub_id,
            parent_id=rows[idx].parent_id,
            item_label=rows[idx].item_label,
            score=score,
            preview=preview_text(rows[idx].content),
            rank=rank,
        )
        for rank, (idx, score) in enumerate(ranked, start=1)
    ]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = OUTPUT_ROOT / f"embed_test_{stamp}"
    report = EmbedTestReport(
        model_id=model_id,
        dimension=EXPECTED_DIMENSION,
        query=query,
        chunk_count=len(rows),
        source=source,
        created_at=now_iso(),
        hits=hits,
    )
    json_path = write_report(out_dir, report)
    print(f"\nReport: {json_path}")
    print(f"HTML:   {out_dir / 'embed_test_report.html'}")

    if open_browser:
        webbrowser.open((out_dir / "embed_test_report.html").resolve().as_uri())

    return out_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Homework: HF embed + cosine retrieval on sub-chunks"
    )
    parser.add_argument(
        "--query",
        default="What are the company's risk factors?",
        help="Test search query",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=8,
        help="Max sub-chunks to embed (default 8)",
    )
    parser.add_argument(
        "--chunks",
        metavar="PATH",
        help=(
            "Path or glob to chunks.json (quote globs: 'output/AAPL_*/chunks.json'). "
            "Prefer --ticker when multiple ingests exist."
        ),
    )
    parser.add_argument(
        "--ticker",
        help="Use latest chunks.json for ticker under homework output (e.g. AAPL)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of top hits to show (default 3)",
    )
    parser.add_argument("--open", action="store_true", help="Open HTML report in browser")
    args = parser.parse_args(argv)

    try:
        if args.chunks and args.ticker:
            raise ValueError("Pass --chunks or --ticker, not both")
        chunks_path = resolve_chunks_path(args.chunks, ticker=args.ticker)
        run_embed_test(
            query=args.query,
            limit=args.limit,
            chunks_path=chunks_path,
            top_k=args.top_k,
            open_browser=args.open,
        )
    except (HuggingFaceEmbedError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
