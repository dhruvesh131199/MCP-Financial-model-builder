"""Session-scoped SEC fetch, filter, and summarize — no global ticker cache."""

from __future__ import annotations

import logging

from ingest.edgar_fetch import EdgarFetchError, fetch_edgar_statements
from ingest.normalize import FinancialStatements, StatementSlice, normalize_company_facts
from services.sec_client import fetch_company_facts, resolve_ticker

logger = logging.getLogger(__name__)

ALL_STATEMENTS = ("income", "balance", "cashflow")


def _normalize_statement_list(statements: list[str] | None) -> list[str]:
    if not statements:
        return list(ALL_STATEMENTS)
    valid = [s for s in statements if s in ALL_STATEMENTS]
    return valid or list(ALL_STATEMENTS)


def build_dedup_key(
    ticker: str,
    *,
    fiscal_years: list[int] | None,
    max_years: int,
    include_annual: bool,
    include_quarterly: bool,
    statements: list[str],
) -> str:
    if fiscal_years:
        years_part = "years=" + ",".join(str(y) for y in sorted(fiscal_years))
    else:
        years_part = f"max_years={max_years}"
    period_flags: list[str] = []
    if include_annual:
        period_flags.append("annual")
    if include_quarterly:
        period_flags.append("quarterly")
    period_part = "+".join(period_flags) or "none"
    stmt_part = "+".join(sorted(statements))
    return f"{ticker.upper()}|{years_part}|{period_part}|{stmt_part}|ingest=edgartools|fetch=statements"


def build_file_name(
    ticker: str,
    *,
    fiscal_years: list[int] | None,
    max_years: int,
) -> str:
    sym = ticker.upper()
    if fiscal_years:
        ys = sorted(fiscal_years)
        if len(ys) == 1:
            return f"{sym} — FY{ys[0]}"
        return f"{sym} — FY{ys[0]}-{ys[-1]}"
    if max_years == 1:
        return f"{sym} — Latest Financials"
    return f"{sym} — {max_years}Y Financials"


def _collect_annual_fiscal_years(financials: FinancialStatements) -> list[int]:
    """Distinct fiscal years from annual periods only (ignore quarterly spillover)."""
    years: set[int] = set()
    for slice_ in financials.statements.values():
        for period in slice_.annual:
            years.add(period.fiscal_year)
    return sorted(years, reverse=True)


def filter_financials(
    financials: FinancialStatements,
    *,
    fiscal_years: list[int] | None = None,
    max_years: int = 1,
    include_annual: bool = True,
    include_quarterly: bool = False,
    statements: list[str] | None = None,
    max_quarterly_periods: int | None = None,
) -> FinancialStatements:
    """Filter statements and trim periods for session storage / dashboard."""
    requested = _normalize_statement_list(statements)
    quarterly_cap = max_quarterly_periods if max_quarterly_periods is not None else max_years * 4

    if fiscal_years:
        allowed_annual_years = set(fiscal_years)
    else:
        allowed_annual_years = set(_collect_annual_fiscal_years(financials)[:max_years])

    trimmed: dict[str, StatementSlice] = {}
    for key in requested:
        slice_ = financials.statements.get(key)
        if not slice_:
            trimmed[key] = StatementSlice()
            continue

        annual = (
            [p for p in slice_.annual if p.fiscal_year in allowed_annual_years]
            if include_annual
            else []
        )
        annual.sort(key=lambda p: (p.fiscal_year, p.fiscal_period), reverse=True)
        if not fiscal_years:
            annual = annual[:max_years]

        quarterly = slice_.quarterly if include_quarterly else []
        if include_quarterly:
            quarterly = sorted(
                quarterly,
                key=lambda p: (p.period_end or "", p.fiscal_year, p.fiscal_period),
                reverse=True,
            )
            quarterly = quarterly[:quarterly_cap]
            if fiscal_years:
                quarterly = [p for p in quarterly if p.fiscal_year in allowed_annual_years]

        trimmed[key] = StatementSlice(annual=annual, quarterly=quarterly)

    return financials.model_copy(
        update={"statements": trimmed, "fetch_scope": requested}
    )


def _fetch_via_companyfacts(
    resolved: dict,
    *,
    fiscal_years: list[int] | None,
    max_years: int,
    include_annual: bool,
    include_quarterly: bool,
    statements: list[str] | None,
) -> FinancialStatements:
    raw = fetch_company_facts(resolved["cik"])
    financials = normalize_company_facts(
        raw,
        ticker=resolved["ticker"],
        cik=resolved["cik"],
        derive=False,
    )
    if resolved.get("entity_name"):
        financials = financials.model_copy(
            update={"entity_name": resolved["entity_name"]}
        )
    return filter_financials(
        financials,
        fiscal_years=fiscal_years,
        max_years=max_years,
        include_annual=include_annual,
        include_quarterly=include_quarterly,
        statements=statements,
        max_quarterly_periods=max_years * 4,
    )


def fetch_sec_financials(
    *,
    company_name: str | None = None,
    ticker: str | None = None,
    fiscal_years: list[int] | None = None,
    max_years: int = 1,
    include_annual: bool = True,
    include_quarterly: bool = False,
    statements: list[str] | None = None,
) -> FinancialStatements:
    """Resolve ticker, fetch via edgartools statements, fallback to companyfacts."""
    resolved = resolve_ticker(company_name=company_name, ticker=ticker)
    if "error" in resolved:
        raise ValueError(resolved["error"])

    stmt_list = _normalize_statement_list(statements)
    sym = resolved["ticker"]

    try:
        financials = fetch_edgar_statements(
            ticker=sym,
            cik=resolved["cik"],
            entity_name=resolved.get("entity_name") or sym,
            max_years=max_years,
            fiscal_years=fiscal_years,
            max_quarterly_periods=max_years * 4,
            include_annual=include_annual,
            include_quarterly=include_quarterly,
            statements=stmt_list,
        )
        return filter_financials(
            financials,
            fiscal_years=fiscal_years,
            max_years=max_years,
            include_annual=include_annual,
            include_quarterly=include_quarterly,
            statements=stmt_list,
            max_quarterly_periods=max_years * 4,
        )
    except (EdgarFetchError, Exception) as exc:
        logger.warning("edgartools fetch failed for %s, using companyfacts: %s", sym, exc)

    try:
        return _fetch_via_companyfacts(
            resolved,
            fiscal_years=fiscal_years,
            max_years=max_years,
            include_annual=include_annual,
            include_quarterly=include_quarterly,
            statements=stmt_list,
        )
    except Exception as exc:
        raise ValueError(f"SEC fetch failed for {sym}: {exc}") from exc


def included_fiscal_years(financials: FinancialStatements) -> list[int]:
    return _collect_annual_fiscal_years(financials)


def financials_summary(
    financials: FinancialStatements,
    *,
    scope_applied: dict | None = None,
) -> dict:
    """Compact summary for LLM tool response — not the full JSON."""
    income = financials.statements.get("income")
    latest_rev = None
    latest_ni = None
    if income and income.annual:
        latest = income.annual[0]
        for li in latest.line_items:
            if li.key == "revenue":
                latest_rev = li.value
            if li.key == "net_income":
                latest_ni = li.value
    payload = {
        "ticker": financials.ticker,
        "entity_name": financials.entity_name,
        "cik": financials.cik,
        "fetched_at": financials.fetched_at,
        "ingest_source": financials.ingest_source,
        "fiscal_years_included": included_fiscal_years(financials),
        "fetch_scope": financials.fetch_scope,
        "annual_periods": {
            k: len(v.annual) for k, v in financials.statements.items()
        },
        "quarterly_periods": {
            k: len(v.quarterly) for k, v in financials.statements.items()
        },
        "latest_annual_revenue_usd": latest_rev,
        "latest_annual_net_income_usd": latest_ni,
    }
    if scope_applied is not None:
        payload["scope_applied"] = scope_applied
    return payload


def build_scope_applied(
    *,
    fiscal_years: list[int] | None,
    max_years: int,
    include_annual: bool,
    include_quarterly: bool,
    statements: list[str],
    financials: FinancialStatements,
) -> dict:
    """Echo request scope + what was stored — helps the host verify the right fetch ran."""
    annual_counts = [len(v.annual) for v in financials.statements.values()]
    quarterly_counts = [len(v.quarterly) for v in financials.statements.values()]
    included = included_fiscal_years(financials)
    quarterly_fys: set[int] = set()
    for slice_ in financials.statements.values():
        for period in slice_.quarterly:
            quarterly_fys.add(period.fiscal_year)

    return {
        "max_years": max_years,
        "fiscal_years_requested": fiscal_years,
        "include_annual": include_annual,
        "include_quarterly": include_quarterly,
        "statements": statements,
        "fiscal_years_included": included,
        "quarterly_fiscal_years_included": sorted(quarterly_fys, reverse=True),
        "annual_period_count": max(annual_counts) if annual_counts else 0,
        "quarterly_period_count": max(quarterly_counts) if quarterly_counts else 0,
        "ingest_source": financials.ingest_source,
    }
