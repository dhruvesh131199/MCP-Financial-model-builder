"""
Trend analysis homework CLI.

Run from backend/:
    python -m homework.trend_analysis.run --ticker AAPL
    python -m homework.trend_analysis.run --ticker WMT --years 5 --open
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

from engine.trend_analysis import build_trend_table, trend_to_dict  # noqa: E402
from homework.detailed_analysis.fetch import fetch_detailed_statements  # noqa: E402
from homework.hero_analysis_explore import _company_fy_end  # noqa: E402
from homework.trend_analysis.report_html import build_trend_html  # noqa: E402
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

    trend = build_trend_table(snapshot, max_years=years)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = OUTPUT_ROOT / f"{result.ticker}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "trend.json").write_text(
        json.dumps(trend_to_dict(trend), indent=2), encoding="utf-8"
    )
    (out_dir / "trend.html").write_text(build_trend_html(trend), encoding="utf-8")

    if open_browser:
        webbrowser.open((out_dir / "trend.html").resolve().as_uri())

    return out_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trend analysis homework CLI")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--open", action="store_true", dest="open_browser")
    args = parser.parse_args(argv)

    out = run(ticker=args.ticker, years=args.years, open_browser=args.open_browser)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
