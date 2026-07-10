"""Orchestrator for the unified fetch_report MCP tool."""

from __future__ import annotations

import logging
import time
from typing import Literal

from helper.rag.fetch_annual import list_10k_fiscal_years
from helper.rag.resolve import resolve_or_ingest_sec
from services.sec_fetch_handler import handle_cached_sec_fetch

logger = logging.getLogger(__name__)

ReportType = Literal["full_report", "just_financials"]


def run_fetch_report(
    session_id: str,
    *,
    report_type: ReportType,
    tickers: list[str],
    years: list[int] | None = None,
    max_years: int = 1,
) -> dict:
    start = time.perf_counter()

    if report_type not in ("full_report", "just_financials"):
        return {
            "error": f"Invalid report_type: {report_type!r}. Must be 'full_report' or 'just_financials'."
        }

    if not tickers:
        return {"error": "tickers list cannot be empty."}

    clean_tickers = [t.strip().upper() for t in tickers if t.strip()]
    if not clean_tickers:
        return {"error": "tickers list must contain valid ticker strings."}

    clamped_max_years = max(1, min(10, max_years))

    results: list[dict] = []
    errors: list[str] = []

    for ticker in clean_tickers:
        if report_type == "just_financials":
            result = handle_cached_sec_fetch(
                session_id,
                company_name=None,
                ticker=ticker,
                fiscal_years=years,
                max_years=clamped_max_years,
                include_annual=True,
                include_quarterly=False,
                statements=["income", "balance", "cashflow"],
            )
            if "error" in result:
                errors.append(f"{ticker}: {result['error']}")
                results.append({"ticker": ticker, "success": False, "error": result["error"]})
            else:
                results.append(
                    {
                        "ticker": ticker,
                        "success": True,
                        "file_id": result.get("file_id"),
                        "scope_applied": result.get("scope_applied"),
                    }
                )
        else:
            # full_report (RAG)
            target_years = years
            if not target_years:
                try:
                    target_years = list_10k_fiscal_years(ticker, clamped_max_years)
                except Exception as exc:
                    errors.append(f"{ticker}: Failed to list 10-K years: {exc}")
                    results.append({"ticker": ticker, "success": False, "error": str(exc)})
                    continue

            if not target_years:
                errors.append(f"{ticker}: No 10-K filings found.")
                results.append({"ticker": ticker, "success": False, "error": "No 10-K filings found."})
                continue

            for year in target_years:
                try:
                    resolved = resolve_or_ingest_sec(
                        session_id=session_id,
                        ticker=ticker,
                        fiscal_year=year,
                    )
                    if not resolved.success:
                        errors.append(f"{ticker} FY{year}: {resolved.error}")
                        results.append(
                            {
                                "ticker": ticker,
                                "year": year,
                                "success": False,
                                "error": resolved.error,
                            }
                        )
                    else:
                        results.append(
                            {
                                "ticker": ticker,
                                "year": year,
                                "success": True,
                                "document_id": resolved.document_id,
                                "filing_key": resolved.filing_key,
                                "from_cache": resolved.from_cache,
                            }
                        )
                except Exception as exc:
                    errors.append(f"{ticker} FY{year}: {exc}")
                    results.append(
                        {
                            "ticker": ticker,
                            "year": year,
                            "success": False,
                            "error": str(exc),
                        }
                    )

    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)
    elapsed_s = time.perf_counter() - start

    timing_msg = (
        f"fetch_report duration={elapsed_s:.2f}s report_type={report_type} "
        f"tickers={clean_tickers} success={success_count}/{total_count}"
    )
    print(timing_msg, flush=True)
    logger.info(
        "fetch_report duration=%.2fs report_type=%s tickers=%s success=%s/%s",
        elapsed_s,
        report_type,
        clean_tickers,
        success_count,
        total_count,
    )

    return {
        "success": len(errors) == 0 and success_count > 0,
        "report_type": report_type,
        "results": results,
        "errors": errors,
        "duration_seconds": round(elapsed_s, 2),
        "message": f"Fetched {success_count}/{total_count} requested reports.",
    }
