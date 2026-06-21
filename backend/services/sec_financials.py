"""Session-scoped SEC fetch, filter, and summarize — no global ticker cache."""

from __future__ import annotations

from ingest.normalize import FinancialStatements, StatementPeriod, StatementSlice, normalize_company_facts
from services.sec_client import fetch_company_facts, resolve_ticker

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
    return f"{ticker.upper()}|{years_part}|{period_part}|{stmt_part}"


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
    return f"{sym} — {max_years}Y Financials"


def _collect_fiscal_years(financials: FinancialStatements) -> list[int]:
    years: set[int] = set()
    for slice_ in financials.statements.values():
        for period in slice_.annual + slice_.quarterly:
            years.add(period.fiscal_year)
    return sorted(years, reverse=True)


def _filter_periods_by_years(
    periods: list[StatementPeriod],
    allowed_years: set[int],
) -> list[StatementPeriod]:
    return [p for p in periods if p.fiscal_year in allowed_years]


def filter_financials(
    financials: FinancialStatements,
    *,
    fiscal_years: list[int] | None = None,
    max_years: int = 5,
    include_annual: bool = True,
    include_quarterly: bool = True,
    statements: list[str] | None = None,
    max_quarterly_periods: int = 20,
) -> FinancialStatements:
    """Filter statements and trim periods for session storage / dashboard."""
    requested = _normalize_statement_list(statements)

    if fiscal_years:
        allowed_years = set(fiscal_years)
    else:
        all_years = _collect_fiscal_years(financials)
        allowed_years = set(all_years[:max_years])

    trimmed: dict[str, StatementSlice] = {}
    for key in requested:
        slice_ = financials.statements.get(key)
        if not slice_:
            trimmed[key] = StatementSlice()
            continue

        annual = (
            _filter_periods_by_years(slice_.annual, allowed_years)
            if include_annual
            else []
        )
        quarterly = slice_.quarterly[:max_quarterly_periods] if include_quarterly else []
        quarterly = _filter_periods_by_years(quarterly, allowed_years)

        trimmed[key] = StatementSlice(annual=annual, quarterly=quarterly)

    return financials.model_copy(
        update={"statements": trimmed, "fetch_scope": requested}
    )


def fetch_sec_financials(
    *,
    company_name: str | None = None,
    ticker: str | None = None,
    fiscal_years: list[int] | None = None,
    max_years: int = 5,
    include_annual: bool = True,
    include_quarterly: bool = True,
    statements: list[str] | None = None,
) -> FinancialStatements:
    """Resolve ticker, fetch from SEC, normalize, and filter."""
    resolved = resolve_ticker(company_name=company_name, ticker=ticker)
    if "error" in resolved:
        raise ValueError(resolved["error"])

    try:
        raw = fetch_company_facts(resolved["cik"])
    except Exception as exc:
        sym = resolved["ticker"]
        raise ValueError(f"SEC fetch failed for {sym}: {exc}") from exc

    financials = normalize_company_facts(
        raw,
        ticker=resolved["ticker"],
        cik=resolved["cik"],
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
    )


def included_fiscal_years(financials: FinancialStatements) -> list[int]:
    years: set[int] = set()
    for slice_ in financials.statements.values():
        for period in slice_.annual + slice_.quarterly:
            years.add(period.fiscal_year)
    return sorted(years)


def financials_summary(financials: FinancialStatements) -> dict:
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
    return {
        "ticker": financials.ticker,
        "entity_name": financials.entity_name,
        "cik": financials.cik,
        "fetched_at": financials.fetched_at,
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
