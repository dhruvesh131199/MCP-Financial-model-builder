"""
RAG + MarkItDown homework CLI.

Run from backend/:
    python -m homework.rag_markitdown.run --ticker AAPL
    python -m homework.rag_markitdown.run --ticker WMT --open
    python -m homework.rag_markitdown.run --upload /path/to/report.pdf
    python -m homework.rag_markitdown.run --batch AAPL,WMT,COST --summary-csv
"""

from __future__ import annotations

import argparse
import csv
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from homework.rag_markitdown.pipeline import ingest_from_sec, ingest_from_upload  # noqa: E402
from homework.rag_markitdown.schema import IngestResult  # noqa: E402
from homework.rag_markitdown.storage import OUTPUT_ROOT  # noqa: E402


def _print_result(result: IngestResult) -> None:
    out = Path(result.output_dir)
    print(f"Output: {out}")
    print(f"  raw:      {result.raw_filename} ({result.raw_bytes:,} bytes)")
    print(f"  markdown: {result.markdown_chars:,} chars, {result.markdown_lines} lines")
    print(f"  format:   {result.source_format.value}")
    if result.section_outline:
        print(f"  items:    {result.section_outline.items_found} Item section(s)")
    if result.narrative_checks:
        print("  narrative checks:", result.narrative_checks)
    print("  report.html")
    print("  sections.json")
    print("  converted.md")


def _write_batch_csv(batch_dir: Path, results: list[IngestResult]) -> Path:
    csv_path = batch_dir / "summary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ticker", "item_id", "title", "chars", "tokens"])
        for result in results:
            ticker = (
                result.filing.ticker if result.filing and result.filing.ticker else "?"
            )
            outline = result.section_outline
            if not outline:
                continue
            rows: list[tuple[str, str, str, int, int]] = []
            if outline.preamble:
                rows.append(
                    (
                        ticker,
                        outline.preamble.item_id,
                        outline.preamble.label,
                        outline.preamble.char_count,
                        outline.preamble.approx_tokens,
                    )
                )
            for item in outline.items:
                rows.append(
                    (
                        ticker,
                        item.item_id,
                        item.label,
                        item.char_count,
                        item.approx_tokens,
                    )
                )
            writer.writerows(rows)
    return csv_path


def run(
    *,
    ticker: str | None = None,
    upload: Path | None = None,
    upload_ticker: str | None = None,
    upload_year: int | None = None,
    upload_doctype: str = "10K",
    batch: list[str] | None = None,
    summary_csv: bool = False,
    open_browser: bool = False,
) -> Path:
    modes = sum(bool(x) for x in (ticker, upload, batch))
    if modes != 1:
        raise ValueError("Pass exactly one of --ticker, --upload, or --batch")

    if batch:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        batch_dir = OUTPUT_ROOT / f"batch_{stamp}"
        batch_dir.mkdir(parents=True, exist_ok=True)
        results: list[IngestResult] = []
        for sym in batch:
            sym = sym.strip().upper()
            if not sym:
                continue
            print(f"\n=== {sym} ===")
            result = ingest_from_sec(ticker=sym, homework_output=True)
            _print_result(result)
            results.append(result)
        if summary_csv:
            csv_path = _write_batch_csv(batch_dir, results)
            print(f"\nBatch summary: {csv_path}")
        if open_browser and results:
            webbrowser.open(
                Path(results[-1].report_html_path).resolve().as_uri()
            )
        return batch_dir

    if ticker:
        result = ingest_from_sec(ticker=ticker, homework_output=True)
    else:
        assert upload is not None
        if not upload_ticker or upload_year is None:
            raise ValueError("--upload requires --upload-ticker and --upload-year")
        result = ingest_from_upload(
            upload_path=upload,
            original_filename=upload.name,
            ticker=upload_ticker,
            year=upload_year,
            doctype=upload_doctype,
            homework_output=True,
        )

    _print_result(result)
    out = Path(result.output_dir)

    if open_browser:
        webbrowser.open((out / "report.html").resolve().as_uri())

    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Homework: 10-K fetch → MarkItDown")
    parser.add_argument("--ticker", help="SEC ticker (latest 10-K)")
    parser.add_argument("--upload", type=Path, help="Local PDF/HTML file to convert")
    parser.add_argument(
        "--upload-ticker",
        help="Ticker for chunk IDs (required with --upload)",
    )
    parser.add_argument(
        "--upload-year",
        type=int,
        help="Filing year for chunk IDs (required with --upload)",
    )
    parser.add_argument(
        "--doctype",
        default="10K",
        help="Document type for chunk IDs (default: 10K)",
    )
    parser.add_argument(
        "--batch",
        help="Comma-separated tickers for multi-company chunk research",
    )
    parser.add_argument(
        "--summary-csv",
        action="store_true",
        help="With --batch, write output/batch_{ts}/summary.csv",
    )
    parser.add_argument("--open", action="store_true", help="Open report.html in browser")
    args = parser.parse_args(argv)

    batch_list = [s.strip() for s in args.batch.split(",")] if args.batch else None

    try:
        run(
            ticker=args.ticker,
            upload=args.upload,
            upload_ticker=args.upload_ticker,
            upload_year=args.upload_year,
            upload_doctype=args.doctype,
            batch=batch_list,
            summary_csv=args.summary_csv,
            open_browser=args.open,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
