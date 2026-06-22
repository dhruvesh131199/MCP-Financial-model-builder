"""
Fetch SEC financials via edgartools statement objects (per filing).

Uses financials.income_statement() / balance_sheet() / cashflow_statement()
on each selected 10-K / 10-Q — no XBRLS stitch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from edgar import Company
from edgar.financials import Financials

from ingest.coverage import build_coverage_report
from ingest.edgar_filing_select import (
    ANNUAL_FORMS,
    QUARTERLY_FORMS,
    scan_head_for_targets,
    select_filings_for_fiscal_years,
    select_recent_quarterly_filings,
)
from ingest.edgar_identity import ensure_edgar_identity
from ingest.fiscal_calendar import (
    fiscal_quarter_from_period_end,
    fiscal_year_from_period_end,
)
from ingest.normalize import (
    FinancialStatements,
    LineItem,
    StatementPeriod,
    StatementSlice,
)
from ingest.statement_extract import (
    STATEMENT_METHODS,
    extract_statement_metrics,
    is_annual_column,
    metrics_to_line_items,
    period_columns,
    period_end_from_col,
    statement_to_dataframe,
)

ALL_STATEMENTS = ("income", "balance", "cashflow")
VIEW = "standard"


class EdgarFetchError(Exception):
    pass


@dataclass
class _FilingBundle:
    financials: Any
    period_end: str
    form: str
    filed: str | None
    is_annual: bool


def _company_fy_end(company: Company) -> str | None:
    for source in (company, getattr(company, "data", None)):
        if source is None:
            continue
        fy = getattr(source, "fiscal_year_end", None)
        if fy:
            return str(fy)
    return None


def _filing_meta(filing: Any) -> tuple[str | None, str | None, str | None]:
    period = getattr(filing, "period_of_report", None)
    period_end = str(period)[:10] if period else None
    form = getattr(filing, "form", None)
    filed = getattr(filing, "filing_date", None)
    filed_s = str(filed)[:10] if filed else None
    return period_end, str(form) if form else None, filed_s


def _frames_from_financials(financials: Any, stmt_keys: list[str]) -> dict[str, Any]:
    frames: dict[str, Any] = {}
    for key in stmt_keys:
        method_name = STATEMENT_METHODS[key]
        method = getattr(financials, method_name, None)
        if method is None:
            continue
        try:
            rendered = method(view=VIEW)
        except TypeError:
            rendered = method()
        df = statement_to_dataframe(rendered, view=VIEW)
        if df is not None and not df.empty:
            frames[key] = df
    return frames


def _bundle_from_financials(
    financials: Any,
    *,
    filing: Any | None,
    form: str,
    is_annual: bool,
) -> _FilingBundle:
    period_end = None
    filed = None
    if filing is not None:
        period_end, form, filed = _filing_meta(filing)
    if not period_end:
        frames = _frames_from_financials(financials, ["income"])
        income = frames.get("income")
        if income is not None:
            cols = period_columns(income)
            if cols:
                period_end = period_end_from_col(cols[0])
    if not period_end:
        raise EdgarFetchError("Could not determine period end from financials")
    return _FilingBundle(
        financials=financials,
        period_end=period_end,
        form=form,
        filed=filed,
        is_annual=is_annual,
    )


def _select_annual_filings(
    company: Company,
    *,
    fiscal_years: list[int] | None,
    max_years: int,
    fy_end_mmdd: str | None,
) -> list[Any]:
    if fiscal_years:
        targets = set(fiscal_years)
        latest_pe = None
        try:
            latest = company.get_filings(form="10-K", amendments=False).latest()
            if latest:
                latest_pe = str(getattr(latest, "period_of_report", ""))[:10]
        except Exception:
            pass
        latest_fy = (
            fiscal_year_from_period_end(latest_pe, fy_end_mmdd=fy_end_mmdd)
            if latest_pe
            else max(targets)
        )
        head = scan_head_for_targets(
            target_fiscal_years=targets,
            quarterly=False,
            latest_fy=latest_fy,
            min_fy=min(targets),
        )
        return select_filings_for_fiscal_years(
            company,
            ANNUAL_FORMS,
            targets,
            quarterly=False,
            fy_end_mmdd=fy_end_mmdd,
            scan_head=head,
        )

    count = max(1, max_years)
    for form in ANNUAL_FORMS:
        try:
            batch = company.get_filings(form=form, amendments=False).head(count)
            if batch:
                return list(batch)
        except Exception:
            continue
    return []


def _select_quarterly_filings(
    company: Company,
    *,
    fiscal_years: list[int] | None,
    max_years: int,
    fy_end_mmdd: str | None,
) -> list[Any]:
    cap = max(1, max_years) * 4
    if fiscal_years:
        targets = set(fiscal_years)
        head = scan_head_for_targets(
            target_fiscal_years=targets,
            quarterly=True,
            latest_fy=max(targets),
            min_fy=min(targets),
        )
        selected = select_filings_for_fiscal_years(
            company,
            QUARTERLY_FORMS,
            targets,
            quarterly=True,
            fy_end_mmdd=fy_end_mmdd,
            scan_head=head,
        )
        return selected[:cap]
    return select_recent_quarterly_filings(company, QUARTERLY_FORMS, cap)


def _period_label(
    period_end: str,
    *,
    is_annual: bool,
    fy_end_mmdd: str | None,
) -> tuple[int, str]:
    fy = fiscal_year_from_period_end(period_end, fy_end_mmdd=fy_end_mmdd)
    if fy is None:
        fy = int(period_end[:4])
    if is_annual:
        return fy, "FY"
    return fy, fiscal_quarter_from_period_end(period_end, fy_end_mmdd=fy_end_mmdd)


def _collect_filing_periods(
    bundle: _FilingBundle,
    stmt_keys: list[str],
    *,
    fy_end_mmdd: str | None,
) -> list[tuple[str, dict[str, list[LineItem]], bool]]:
    frames = _frames_from_financials(bundle.financials, stmt_keys)
    if not frames:
        return []

    cols: set[str] = set()
    for df in frames.values():
        cols.update(period_columns(df))
    if not cols:
        return []

    out: list[tuple[str, dict[str, list[LineItem]], bool]] = []
    for col in sorted(cols, key=period_end_from_col, reverse=True):
        annual = is_annual_column(col) or bundle.is_annual
        by_stmt: dict[str, list[LineItem]] = {}
        for key in stmt_keys:
            df = frames.get(key)
            if df is None or col not in df.columns:
                continue
            metrics = extract_statement_metrics(df, col, key)
            if not metrics:
                continue
            by_stmt[key] = [
                LineItem(**item) for item in metrics_to_line_items(metrics, key)
            ]
        if by_stmt:
            out.append((col, by_stmt, annual))
    return out


def fetch_edgar_statements(
    *,
    ticker: str,
    cik: str,
    entity_name: str,
    max_years: int = 1,
    fiscal_years: list[int] | None = None,
    max_quarterly_periods: int | None = None,
    include_annual: bool = True,
    include_quarterly: bool = False,
    statements: list[str] | None = None,
) -> FinancialStatements:
    """Fetch and normalize SEC statements for one company."""
    ensure_edgar_identity()
    stmt_keys = list(statements or ALL_STATEMENTS)
    stmt_keys = [s for s in stmt_keys if s in ALL_STATEMENTS] or list(ALL_STATEMENTS)

    company = Company(ticker)
    fy_end = _company_fy_end(company)
    bundles: list[_FilingBundle] = []
    warnings: list[str] = []

    use_fast_annual = (
        include_annual
        and not include_quarterly
        and not fiscal_years
        and max_years == 1
    )

    if use_fast_annual:
        fin = company.get_financials()
        if fin is None:
            raise EdgarFetchError(f"No annual financials for {ticker}")
        bundles.append(
            _bundle_from_financials(fin, filing=None, form="10-K", is_annual=True)
        )
    else:
        if include_annual:
            for filing in _select_annual_filings(
                company,
                fiscal_years=fiscal_years,
                max_years=max_years,
                fy_end_mmdd=fy_end,
            ):
                fin = Financials.extract(filing)
                if fin is None:
                    warnings.append(
                        f"XBRL missing: {getattr(filing, 'accession_no', filing)}"
                    )
                    continue
                bundles.append(
                    _bundle_from_financials(
                        fin,
                        filing=filing,
                        form=str(getattr(filing, "form", "10-K")),
                        is_annual=True,
                    )
                )
            if include_annual and fiscal_years and not bundles:
                warnings.append(f"No annual filings for fiscal years {fiscal_years}")

        if include_quarterly:
            for filing in _select_quarterly_filings(
                company,
                fiscal_years=fiscal_years,
                max_years=max_years,
                fy_end_mmdd=fy_end,
            ):
                fin = Financials.extract(filing)
                if fin is None:
                    warnings.append(
                        f"XBRL missing: {getattr(filing, 'accession_no', filing)}"
                    )
                    continue
                bundles.append(
                    _bundle_from_financials(
                        fin,
                        filing=filing,
                        form=str(getattr(filing, "form", "10-Q")),
                        is_annual=False,
                    )
                )

    if not bundles:
        raise EdgarFetchError(f"No financial statements retrieved for {ticker}")

    annual_store: dict[str, dict[str, StatementPeriod]] = {k: {} for k in stmt_keys}
    quarterly_store: dict[str, dict[str, StatementPeriod]] = {k: {} for k in stmt_keys}

    for bundle in bundles:
        for period_col, items_by_stmt, col_is_annual in _collect_filing_periods(
            bundle, stmt_keys, fy_end_mmdd=fy_end
        ):
            period_end = period_end_from_col(period_col)
            is_annual = bundle.is_annual and col_is_annual
            fy, fp = _period_label(period_end, is_annual=is_annual, fy_end_mmdd=fy_end)
            if fiscal_years and fy not in fiscal_years:
                continue

            dedupe = f"{period_end}|{fp}"
            store = annual_store if is_annual else quarterly_store

            for stmt_key, line_items in items_by_stmt.items():
                if dedupe not in store[stmt_key]:
                    store[stmt_key][dedupe] = StatementPeriod(
                        fiscal_year=fy,
                        fiscal_period=fp,
                        period_end=period_end,
                        filed=bundle.filed,
                        form=bundle.form,
                        line_items=line_items,
                    )

    q_cap = max_quarterly_periods if max_quarterly_periods is not None else max_years * 4
    statements_out: dict[str, StatementSlice] = {}
    for key in stmt_keys:
        annual = sorted(
            annual_store[key].values(),
            key=lambda p: (p.period_end or "", p.fiscal_year, p.fiscal_period),
            reverse=True,
        )
        quarterly = sorted(
            quarterly_store[key].values(),
            key=lambda p: (p.period_end or "", p.fiscal_year, p.fiscal_period),
            reverse=True,
        )
        if not fiscal_years and include_annual:
            annual = annual[:max_years]
        if include_quarterly:
            quarterly = quarterly[:q_cap]
        statements_out[key] = StatementSlice(annual=annual, quarterly=quarterly)

    result = FinancialStatements(
        ticker=ticker.upper(),
        cik=cik,
        entity_name=entity_name,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        statements=statements_out,
        fetch_scope=stmt_keys,
        ingest_source="edgartools",
    )

    income = statements_out.get("income")
    fy_cov = None
    if income and income.annual:
        fy_cov = income.annual[0].fiscal_year
    elif income and income.quarterly:
        fy_cov = income.quarterly[0].fiscal_year
    if fy_cov is not None:
        cov = build_coverage_report(result.model_dump(), fy_cov)
        result = result.model_copy(update={"coverage": cov})

    return result


# Back-compat alias used by integration tests during transition
def fetch_edgar_frames(**kwargs: Any) -> FinancialStatements:
    """Deprecated name — returns FinancialStatements directly."""
    return fetch_edgar_statements(**kwargs)
