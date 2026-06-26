"""
Hugging Face vs edgartools — income statement normalization (homework only).

Not linked from the product UI. Outputs stay under homework/huggingface_test/output/ (gitignored).
HF may be reused for other experiments later.

Run from backend/:
  python -m homework.huggingface_test.run_test --fetch-only
  python -m homework.huggingface_test.run_test --limit 3
  python -m homework.huggingface_test.run_test --open
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from ingest.edgar_identity import ensure_edgar_identity  # noqa: E402

from homework.huggingface_test.fetch_income import (  # noqa: E402
    baseline_to_dict,
    fetch_latest_income_baseline,
)
from homework.huggingface_test.hf_client import (  # noqa: E402
    DEFAULT_MODEL,
    HuggingFaceError,
    call_hf_normalizer,
)
from homework.huggingface_test.prompts import (  # noqa: E402
    STANDARD_BUCKETS,
    SYSTEM_PROMPT,
    build_chat_messages,
)
from homework.huggingface_test.report_html import write_report_html  # noqa: E402
from homework.huggingface_test.tickers import TICKERS_50  # noqa: E402

OUTPUT_ROOT = Path(__file__).resolve().parent / "output"


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _bucket_value(mapped: list[dict[str, Any]] | None, bucket: str) -> Any:
    if not mapped:
        return None
    for item in mapped:
        if item.get("standard_concept") == bucket:
            return item.get("value")
    return None


def _review_rows_for_ticker(
    baseline: dict[str, Any],
    hf_mapped: list[dict[str, Any]] | None,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    ticker = baseline["ticker"]
    for bucket in STANDARD_BUCKETS:
        edgar_ref = ""
        if bucket == "Revenue" and baseline.get("smart_revenue_usd") is not None:
            edgar_ref = str(baseline["smart_revenue_usd"])
        hf_val = _bucket_value(hf_mapped, bucket)
        rows.append(
            {
                "ticker": ticker,
                "entity_name": str(baseline.get("entity_name", "")),
                "fiscal_year": str(baseline.get("fiscal_year", "")),
                "standard_concept": bucket,
                "edgartools_reference": edgar_ref,
                "hf_mapped_value": "" if hf_val is None else str(hf_val),
                "manual_truth": "",
                "hf_matches_manual": "",
                "edgartools_matches_manual": "",
                "notes": "",
            }
        )
    return rows


def _write_review_sheet(path: Path, all_rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "ticker",
        "entity_name",
        "fiscal_year",
        "standard_concept",
        "edgartools_reference",
        "hf_mapped_value",
        "manual_truth",
        "hf_matches_manual",
        "edgartools_matches_manual",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)


def run_batch(
    *,
    tickers: list[str],
    output_dir: Path,
    fetch_only: bool,
    model_id: str,
    sleep_s: float,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "run_id": output_dir.name,
        "started_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "fetch_only": fetch_only,
        "model_id": model_id if not fetch_only else None,
        "ticker_count": len(tickers),
        "results": [],
    }
    review_rows: list[dict[str, str]] = []

    for i, ticker in enumerate(tickers, start=1):
        sym = ticker.upper()
        ticker_dir = output_dir / sym
        ticker_dir.mkdir(parents=True, exist_ok=True)
        entry: dict[str, Any] = {"ticker": sym, "status": "pending"}

        print(f"[{i}/{len(tickers)}] {sym} …", flush=True)

        try:
            baseline = fetch_latest_income_baseline(sym)
            baseline_dict = baseline_to_dict(baseline)
            _write_json(ticker_dir / "baseline.json", baseline_dict)
            _write_json(ticker_dir / "line_items.json", baseline.line_items)

            messages = build_chat_messages(baseline)
            (ticker_dir / "system_prompt.txt").write_text(
                messages["system"], encoding="utf-8"
            )
            (ticker_dir / "user_message.txt").write_text(
                messages["user"], encoding="utf-8"
            )

            hf_mapped = None
            if fetch_only:
                entry["status"] = "baseline_only"
            else:
                hf_result = call_hf_normalizer(
                    system=messages["system"],
                    user=messages["user"],
                    model_id=model_id,
                )
                _write_json(ticker_dir / "hf_response.json", hf_result)
                hf_mapped = hf_result.get("parsed_array")
                if hf_mapped is not None:
                    _write_json(ticker_dir / "hf_mapped.json", hf_mapped)
                if hf_result.get("parse_error"):
                    entry["status"] = "hf_parse_error"
                    entry["parse_error"] = hf_result["parse_error"]
                else:
                    entry["status"] = "ok"

            review_rows.extend(_review_rows_for_ticker(baseline_dict, hf_mapped))
            entry["fiscal_year"] = baseline.fiscal_year
            entry["smart_revenue_usd"] = baseline.smart_revenue_usd
            entry["line_item_count"] = len(baseline.line_items)
            entry["mapped_bucket_count"] = len(hf_mapped) if hf_mapped else 0

        except HuggingFaceError as exc:
            entry["status"] = "hf_error"
            entry["error"] = str(exc)
            print(f"  HF error: {exc}", file=sys.stderr)
        except Exception as exc:
            entry["status"] = "error"
            entry["error"] = str(exc)
            print(f"  error: {exc}", file=sys.stderr)

        manifest["results"].append(entry)

        if not fetch_only and i < len(tickers) and sleep_s > 0:
            time.sleep(sleep_s)

    manifest["finished_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    _write_json(output_dir / "manifest.json", manifest)
    _write_review_sheet(output_dir / "review_sheet.csv", review_rows)
    report_path = write_report_html(manifest=manifest, output_dir=output_dir)

    ok = sum(1 for r in manifest["results"] if r["status"] in ("ok", "baseline_only"))
    print(f"\nDone: {ok}/{len(tickers)} succeeded")
    print(f"Report: {report_path}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="HF income statement normalization test (homework)"
    )
    parser.add_argument("--ticker", help="Single ticker (default: all 50)")
    parser.add_argument("--limit", type=int, help="First N tickers from universe")
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Fetch edgartools baselines + HTML only; skip HF API",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"HF model id (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Seconds between HF requests (default: 1.0)",
    )
    parser.add_argument("--output-dir", type=Path, help="Override output directory")
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open report.html in browser after run",
    )
    args = parser.parse_args()

    ensure_edgar_identity()

    if args.ticker:
        tickers = [args.ticker.upper()]
    else:
        tickers = list(TICKERS_50)
        if args.limit:
            tickers = tickers[: args.limit]

    out_dir = args.output_dir or (OUTPUT_ROOT / _run_id())

    if not args.fetch_only:
        try:
            from homework.huggingface_test.hf_client import get_hf_token

            get_hf_token()
        except HuggingFaceError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            print("Use --fetch-only to build baselines without HF token.", file=sys.stderr)
            return 1

    run_batch(
        tickers=tickers,
        output_dir=out_dir,
        fetch_only=args.fetch_only,
        model_id=args.model,
        sleep_s=args.sleep,
    )

    if args.open:
        report = out_dir / "report.html"
        if report.exists():
            webbrowser.open(report.as_uri())

    return 0


if __name__ == "__main__":
    sys.exit(main())
