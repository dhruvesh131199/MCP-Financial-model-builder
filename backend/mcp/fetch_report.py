"""Orchestrator for the unified fetch_report MCP tool."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Literal

from helper.rag.fetch_annual import list_10k_fiscal_years
from helper.rag.resolve import RagResolveResult, resolve_or_ingest_sec_async
from services.sec_fetch_handler import handle_cached_sec_fetch

logger = logging.getLogger(__name__)

ReportType = Literal["full_report", "just_financials"]


def _resolve_result_to_dict(resolved: RagResolveResult) -> dict:
    if not resolved.success:
        out: dict = {
            "ticker": resolved.ticker,
            "success": False,
            "error": resolved.error,
        }
        if resolved.year is not None:
            out["year"] = resolved.year
        return out
    return {
        "ticker": resolved.ticker,
        "year": resolved.year,
        "success": True,
        "document_id": resolved.document_id,
        "filing_key": resolved.filing_key,
        "from_cache": resolved.from_cache,
    }


async def _process_ticker_year_async(
    session_id: str, ticker: str, year: int
) -> dict:
    try:
        resolved = await resolve_or_ingest_sec_async(
            session_id=session_id,
            ticker=ticker,
            fiscal_year=year,
        )
        return _resolve_result_to_dict(resolved)
    except Exception as exc:
        return {
            "ticker": ticker,
            "year": year,
            "success": False,
            "error": str(exc),
        }


def _map_full_report_work_items(
    clean_tickers: list[str],
    years: list[int] | None,
    clamped_max_years: int,
) -> tuple[list[tuple[str, int]], list[dict], list[str]]:
    work_items: list[tuple[str, int]] = []
    results: list[dict] = []
    errors: list[str] = []

    for ticker in clean_tickers:
        target_years = years
        if not target_years:
            try:
                target_years = list_10k_fiscal_years(ticker, clamped_max_years)
            except Exception as exc:
                msg = f"{ticker}: Failed to list 10-K years: {exc}"
                errors.append(msg)
                results.append({"ticker": ticker, "success": False, "error": str(exc)})
                continue

        if not target_years:
            msg = f"{ticker}: No 10-K filings found."
            errors.append(msg)
            results.append({"ticker": ticker, "success": False, "error": "No 10-K filings found."})
            continue

        for year in target_years:
            work_items.append((ticker, year))

    return work_items, results, errors


async def run_fetch_report_async(
    session_id: str,
    *,
    report_type: ReportType,
    tickers: list[str],
    years: list[int] | None = None,
    max_years: int = 1,
) -> dict:
    """Fetch SEC tables or full 10-K narratives for one or more tickers.

    Use when: MCP `fetch_report` or dashboard asks for financials / RAG corpus.
    Logic: validate tickers → for full_report, gather parallel 10-K ingests per (ticker, year).
    Returns: e.g. {"success": True, "results": [...], "duration_seconds": 12.5, "message": "Fetched 2/2 ..."}
    """
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

    if report_type == "just_financials":
        for ticker in clean_tickers:
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
        work_items, pre_results, pre_errors = _map_full_report_work_items(
            clean_tickers, years, clamped_max_years
        )
        results.extend(pre_results)
        errors.extend(pre_errors)

        if work_items:
            outcomes = await asyncio.gather(
                *[
                    _process_ticker_year_async(session_id, ticker, year)
                    for ticker, year in work_items
                ],
                return_exceptions=True,
            )
            for (ticker, year), outcome in zip(work_items, outcomes, strict=True):
                if isinstance(outcome, BaseException):
                    msg = f"{ticker} FY{year}: {outcome}"
                    errors.append(msg)
                    results.append(
                        {
                            "ticker": ticker,
                            "year": year,
                            "success": False,
                            "error": str(outcome),
                        }
                    )
                elif not outcome["success"]:
                    errors.append(f"{ticker} FY{year}: {outcome['error']}")
                    results.append(outcome)
                else:
                    results.append(outcome)

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


def run_fetch_report(
    session_id: str,
    *,
    report_type: ReportType,
    tickers: list[str],
    years: list[int] | None = None,
    max_years: int = 1,
) -> dict:
    return asyncio.run(
        run_fetch_report_async(
            session_id,
            report_type=report_type,
            tickers=tickers,
            years=years,
            max_years=max_years,
        )
    )
