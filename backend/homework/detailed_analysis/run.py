"""
Detailed Analysis — Phase 1 homework CLI.

Run from backend/:
    python -m homework.detailed_analysis.run --ticker AAPL
    python -m homework.detailed_analysis.run --ticker JPM --years 5 --open
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from edgar import Company  # noqa: E402

from homework.detailed_analysis.fetch import fetch_detailed_statements  # noqa: E402
from homework.detailed_analysis.report_html import (  # noqa: E402
    build_report_html,
    build_validation_md,
)
from homework.detailed_analysis.schema import snapshot_to_dict  # noqa: E402
from homework.hero_analysis_explore import _company_fy_end  # noqa: E402
from ingest.detailed_extract import build_detailed_snapshot  # noqa: E402
from ingest.edgar_identity import ensure_edgar_identity  # noqa: E402

OUTPUT_ROOT = Path(__file__).resolve().parent / "output"


def run(*, ticker: str, years: int = 5, open_browser: bool = False) -> Path:
    ensure_edgar_identity()
    result = fetch_detailed_statements(ticker=ticker, years=years)
    company = Company(ticker.strip().upper())
    fy_end_mmdd = _company_fy_end(company)

    income_tables = result.statements.get("income")
    balance_tables = result.statements.get("balance")
    cashflow_tables = result.statements.get("cashflow")
    income_std = income_tables.standard if income_tables else None
    balance_std = balance_tables.standard if balance_tables else None
    cashflow_std = cashflow_tables.standard if cashflow_tables else None

    if income_std is None and balance_std is None and cashflow_std is None:
        raise ValueError(
            "No stitched statement tables — XBRLS may have failed; "
            "detailed analysis requires wide annual tables"
        )

    snapshot = build_detailed_snapshot(
        ticker=result.ticker,
        entity_name=result.entity_name,
        cik=result.cik,
        fetched_at=result.fetched_at,
        source=result.source,
        income_df=income_std,
        balance_df=balance_std,
        cashflow_df=cashflow_std,
        fy_end_mmdd=fy_end_mmdd,
        max_periods=years,
        warnings=result.warnings,
    )

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = OUTPUT_ROOT / f"{result.ticker}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "analysis.json").write_text(
        json.dumps(snapshot_to_dict(snapshot), indent=2), encoding="utf-8"
    )
    (out_dir / "report.html").write_text(
        build_report_html(snapshot), encoding="utf-8"
    )
    (out_dir / "validation.md").write_text(
        build_validation_md(snapshot), encoding="utf-8"
    )

    print(f"Wrote {out_dir}")
    print("  analysis.json")
    print("  report.html")
    print("  validation.md")
    if snapshot.integrity_checks:
        print("Integrity notes:")
        for note in snapshot.integrity_checks:
            print(f"  - {note}")

    if open_browser:
        webbrowser.open((out_dir / "report.html").resolve().as_uri())

    return out_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detailed analysis homework runner")
    parser.add_argument("--ticker", required=True, help="Stock ticker, e.g. AAPL")
    parser.add_argument("--years", type=int, default=5, help="Annual periods (max 5)")
    parser.add_argument("--open", action="store_true", help="Open report.html in browser")
    args = parser.parse_args(argv)

    try:
        run(ticker=args.ticker, years=min(args.years, 5), open_browser=args.open)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
