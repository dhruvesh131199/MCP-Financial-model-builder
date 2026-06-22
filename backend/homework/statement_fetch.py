"""
Homework runner for SEC fetch scenarios — uses production ingest modules.

Run: python -m homework.statement_fetch
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from edgar import Company
from edgar.financials import Financials
from pydantic import BaseModel, Field

load_dotenv()

from ingest.statement_extract import (  # noqa: E402
    STATEMENT_METHODS,
    extract_statement_metrics,
    is_annual_column,
    metrics_to_line_items,
    period_columns,
    period_end_from_col,
    statement_to_dataframe,
)
from ingest.edgar_filing_select import (  # noqa: E402
    ANNUAL_FORMS,
    QUARTERLY_FORMS,
    scan_head_for_targets,
    select_filings_for_fiscal_years,
    select_recent_quarterly_filings,
)
from ingest.edgar_identity import ensure_edgar_identity  # noqa: E402
from ingest.fiscal_calendar import (  # noqa: E402
    fiscal_quarter_from_period_end,
    fiscal_year_from_period_end,
)
from services.sec_client import resolve_ticker  # noqa: E402

ALL_STATEMENTS = ("income", "balance", "cashflow")
VIEW = "standard"


class LineItemOut(BaseModel):
    key: str
    label: str
    value: float
    unit: str = "USD"
    source: str = "xbrl"
    xbrl_tag: str | None = None


class PeriodOut(BaseModel):
    fiscal_year: int
    fiscal_period: str
    period_end: str
    filed: str | None = None
    form: str | None = None
    line_items: dict[str, list[LineItemOut]] = Field(default_factory=dict)


class StatementSliceOut(BaseModel):
    annual: list[PeriodOut] = Field(default_factory=list)
    quarterly: list[PeriodOut] = Field(default_factory=list)


class StatementFetchResult(BaseModel):
    ticker: str
    cik: str
    entity_name: str
    fetched_at: str
    ingest_source: str = "edgartools_statements"
    fetch_scope: list[str]
    statements: dict[str, StatementSliceOut]
    scope_applied: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


@dataclass
class _FilingPeriod:
    filing: Any | None
    financials: Any
    period_end: str
    form: str
    filed: str | None
    is_annual: bool


class StatementFetchError(Exception):
    pass


def _normalize_statements(statements: list[str] | None) -> list[str]:
    if not statements:
        return list(ALL_STATEMENTS)
    valid = [s for s in statements if s in ALL_STATEMENTS]
    return valid or list(ALL_STATEMENTS)


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


def _financials_from_filing(filing: Any) -> Any | None:
    return Financials.extract(filing)


def _financials_latest_annual(company: Company) -> Any:
    fin = company.get_financials()
    if fin is None:
        raise StatementFetchError("No annual financials from company.get_financials()")
    return fin


def _financials_latest_quarterly(company: Company) -> Any:
    fin = company.get_quarterly_financials()
    if fin is None:
        raise StatementFetchError(
            "No quarterly financials from company.get_quarterly_financials()"
        )
    return fin


def _frames_from_financials(
    financials: Any,
    stmt_keys: list[str],
    *,
    view: str = VIEW,
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for key in stmt_keys:
        method_name = STATEMENT_METHODS[key]
        method = getattr(financials, method_name, None)
        if method is None:
            continue
        try:
            rendered = method(view=view)
        except TypeError:
            rendered = method()
        df = statement_to_dataframe(rendered, view=view)
        if df is not None and not df.empty:
            frames[key] = df
    return frames


def _extract_period_from_frames(
    frames: dict[str, pd.DataFrame],
    period_col: str,
    stmt_keys: list[str],
) -> dict[str, list[LineItemOut]]:
    out: dict[str, list[LineItemOut]] = {}
    for key in stmt_keys:
        df = frames.get(key)
        if df is None or period_col not in df.columns:
            continue
        metrics = extract_statement_metrics(df, period_col, key)
        out[key] = [LineItemOut(**item) for item in metrics_to_line_items(metrics, key)]
    return out


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
    q = fiscal_quarter_from_period_end(period_end, fy_end_mmdd=fy_end_mmdd)
    return fy, q


def _collect_periods_from_financials(
    bundle: _FilingPeriod,
    stmt_keys: list[str],
    *,
    fy_end_mmdd: str | None,
) -> list[tuple[str, dict[str, list[LineItemOut]], bool]]:
    """Return (period_col, line_items_by_statement, is_annual) per column."""
    frames = _frames_from_financials(bundle.financials, stmt_keys)
    if not frames:
        return []

    # Union period columns across statements
    cols: set[str] = set()
    for df in frames.values():
        cols.update(period_columns(df))
    if not cols:
        return []

    results: list[tuple[str, dict[str, list[LineItemOut]], bool]] = []
    for col in sorted(cols, key=period_end_from_col, reverse=True):
        annual = is_annual_column(col) or bundle.is_annual
        items = _extract_period_from_frames(frames, col, stmt_keys)
        if items:
            results.append((col, items, annual))
    return results


def _bundle_from_financials(
    financials: Any,
    *,
    filing: Any | None,
    form: str,
    is_annual: bool,
) -> _FilingPeriod:
    period_end = None
    filed = None
    if filing is not None:
        period_end, form, filed = _filing_meta(filing)
    if not period_end:
        # Infer from first statement column
        frames = _frames_from_financials(financials, ["income"])
        if frames.get("income") is not None:
            cols = period_columns(frames["income"])
            if cols:
                period_end = period_end_from_col(cols[0])
    if not period_end:
        raise StatementFetchError("Could not determine period end from financials")
    return _FilingPeriod(
        filing=filing,
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
    filings: list[Any] = []
    for form in ANNUAL_FORMS:
        try:
            batch = company.get_filings(form=form, amendments=False).head(count)
            if batch:
                filings = list(batch)
                break
        except Exception:
            continue
    return filings


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
        latest_fy = max(targets)
        head = scan_head_for_targets(
            target_fiscal_years=targets,
            quarterly=True,
            latest_fy=latest_fy,
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


def _build_scope_applied(
    *,
    fiscal_years: list[int] | None,
    max_years: int,
    include_annual: bool,
    include_quarterly: bool,
    statements: list[str],
    result: StatementFetchResult,
) -> dict[str, Any]:
    annual_fys: set[int] = set()
    quarterly_fys: set[int] = set()
    for slice_ in result.statements.values():
        for p in slice_.annual:
            annual_fys.add(p.fiscal_year)
        for p in slice_.quarterly:
            quarterly_fys.add(p.fiscal_year)
    annual_counts = [len(v.annual) for v in result.statements.values()]
    quarterly_counts = [len(v.quarterly) for v in result.statements.values()]
    return {
        "max_years": max_years,
        "fiscal_years_requested": fiscal_years,
        "include_annual": include_annual,
        "include_quarterly": include_quarterly,
        "statements": statements,
        "fiscal_years_included": sorted(annual_fys, reverse=True),
        "quarterly_fiscal_years_included": sorted(quarterly_fys, reverse=True),
        "annual_period_count": max(annual_counts) if annual_counts else 0,
        "quarterly_period_count": max(quarterly_counts) if quarterly_counts else 0,
        "ingest_source": result.ingest_source,
        "fetch_mode": "per_filing_statements",
    }


def fetch_sec_financials(
    *,
    company_name: str | None = None,
    ticker: str | None = None,
    fiscal_years: list[int] | None = None,
    max_years: int = 1,
    include_annual: bool = True,
    include_quarterly: bool = False,
    statements: list[str] | None = None,
) -> StatementFetchResult:
    """
    Homework fetch — same parameter surface as MCP fetch_sec_financials.

    Uses financials.income_statement() / balance_sheet() / cashflow_statement()
    on each selected filing (or company.get_financials() for default latest annual).
    """
    resolved = resolve_ticker(company_name=company_name, ticker=ticker)
    if "error" in resolved:
        raise ValueError(resolved["error"])

    stmt_keys = _normalize_statements(statements)
    sym = resolved["ticker"]
    company = Company(sym)
    fy_end = _company_fy_end(company)
    warnings: list[str] = []

    bundles: list[_FilingPeriod] = []

    # Fast path: default latest annual only
    use_fast_annual = (
        include_annual
        and not include_quarterly
        and not fiscal_years
        and max_years == 1
    )

    if use_fast_annual:
        fin = _financials_latest_annual(company)
        bundles.append(
            _bundle_from_financials(fin, filing=None, form="10-K", is_annual=True)
        )
    else:
        if include_annual:
            annual_filings = _select_annual_filings(
                company,
                fiscal_years=fiscal_years,
                max_years=max_years,
                fy_end_mmdd=fy_end,
            )
            if not annual_filings and fiscal_years:
                warnings.append(
                    f"No annual filings found for fiscal years {fiscal_years}"
                )
            for filing in annual_filings:
                fin = _financials_from_filing(filing)
                if fin is None:
                    warnings.append(f"XBRL missing on annual filing {getattr(filing, 'accession_no', filing)}")
                    continue
                bundles.append(
                    _bundle_from_financials(
                        fin,
                        filing=filing,
                        form=str(getattr(filing, "form", "10-K")),
                        is_annual=True,
                    )
                )

        if include_quarterly:
            q_filings = _select_quarterly_filings(
                company,
                fiscal_years=fiscal_years,
                max_years=max_years,
                fy_end_mmdd=fy_end,
            )
            if not q_filings:
                warnings.append("No quarterly filings found for requested scope")
            for filing in q_filings:
                fin = _financials_from_filing(filing)
                if fin is None:
                    warnings.append(
                        f"XBRL missing on quarterly filing {getattr(filing, 'accession_no', filing)}"
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
        raise StatementFetchError(f"No financial statements retrieved for {sym}")

    # Aggregate periods per statement key
    annual_by_key: dict[str, dict[str, PeriodOut]] = {
        k: {} for k in stmt_keys
    }
    quarterly_by_key: dict[str, dict[str, PeriodOut]] = {
        k: {} for k in stmt_keys
    }

    for bundle in bundles:
        extracted = _collect_periods_from_financials(
            bundle, stmt_keys, fy_end_mmdd=fy_end
        )
        for period_col, items_by_stmt, col_is_annual in extracted:
            period_end = period_end_from_col(period_col)
            is_annual = bundle.is_annual and col_is_annual
            fy, fp = _period_label(period_end, is_annual=is_annual, fy_end_mmdd=fy_end)

            if fiscal_years and fy not in fiscal_years:
                continue

            dedupe_key = f"{period_end}|{fp}"
            bucket_annual = is_annual
            target_maps = annual_by_key if bucket_annual else quarterly_by_key

            for stmt_key in stmt_keys:
                line_items = items_by_stmt.get(stmt_key, [])
                if not line_items:
                    continue
                store = target_maps[stmt_key]
                if dedupe_key not in store:
                    store[dedupe_key] = PeriodOut(
                        fiscal_year=fy,
                        fiscal_period=fp,
                        period_end=period_end,
                        filed=bundle.filed,
                        form=bundle.form,
                        line_items={stmt_key: line_items},
                    )
                else:
                    store[dedupe_key].line_items[stmt_key] = line_items

    statements_out: dict[str, StatementSliceOut] = {}
    for key in stmt_keys:
        annual = sorted(
            annual_by_key[key].values(),
            key=lambda p: (p.period_end, p.fiscal_period),
            reverse=True,
        )
        quarterly = sorted(
            quarterly_by_key[key].values(),
            key=lambda p: (p.period_end, p.fiscal_period),
            reverse=True,
        )
        if not fiscal_years and include_annual:
            annual = annual[:max_years]
        if include_quarterly:
            quarterly = quarterly[: max_years * 4]
        statements_out[key] = StatementSliceOut(annual=annual, quarterly=quarterly)

    entity = resolved.get("entity_name") or getattr(company, "name", sym)
    result = StatementFetchResult(
        ticker=sym,
        cik=resolved["cik"],
        entity_name=str(entity),
        fetched_at=datetime.now(timezone.utc).isoformat(),
        fetch_scope=stmt_keys,
        statements=statements_out,
        scope_applied={},
        warnings=warnings,
    )
    result.scope_applied = _build_scope_applied(
        fiscal_years=fiscal_years,
        max_years=max_years,
        include_annual=include_annual,
        include_quarterly=include_quarterly,
        statements=stmt_keys,
        result=result,
    )
    return result


# ---------------------------------------------------------------------------
# Helpers for tests / CLI
# ---------------------------------------------------------------------------
def _metric(result: StatementFetchResult, key: str) -> float | None:
    income = result.statements.get("income")
    if not income or not income.annual:
        if income and income.quarterly:
            period = income.quarterly[0]
        else:
            return None
    else:
        period = income.annual[0]
    for items in period.line_items.values():
        for li in items:
            if li.key == key:
                return li.value
    return None


def _annual_years(result: StatementFetchResult) -> list[int]:
    years: set[int] = set()
    for slice_ in result.statements.values():
        for p in slice_.annual:
            years.add(p.fiscal_year)
    return sorted(years, reverse=True)


def _quarterly_labels(result: StatementFetchResult) -> list[str]:
    labels: list[str] = []
    income = result.statements.get("income")
    if not income:
        return labels
    for p in income.quarterly:
        labels.append(f"FY{p.fiscal_year}-{p.fiscal_period}")
    return labels


@dataclass
class Scenario:
    name: str
    kwargs: dict[str, Any]
    checks: list[str] = field(default_factory=list)
    ticker: str = "AAPL"


SCENARIOS: list[Scenario] = [
    Scenario(
        name="latest_annual_default",
        ticker="AAPL",
        kwargs={},
        checks=["annual_count=1", "has_revenue", "no_quarterly"],
    ),
    Scenario(
        name="specific_fy_2023",
        ticker="AAPL",
        kwargs={"fiscal_years": [2023]},
        checks=["annual_count=1", "fy_included=2023", "has_revenue"],
    ),
    Scenario(
        name="last_3_annual",
        ticker="AAPL",
        kwargs={"max_years": 3},
        checks=["annual_count>=3", "has_revenue"],
    ),
    Scenario(
        name="quarterly_only_last_4",
        ticker="AAPL",
        kwargs={"include_annual": False, "include_quarterly": True, "max_years": 1},
        checks=["no_annual", "quarterly_count>=4", "has_revenue"],
    ),
    Scenario(
        name="annual_and_quarterly_2y",
        ticker="AAPL",
        kwargs={"max_years": 2, "include_annual": True, "include_quarterly": True},
        checks=["annual_count>=2", "quarterly_count>=4", "has_revenue"],
    ),
    Scenario(
        name="fy2023_quarterly_only",
        ticker="AMD",
        kwargs={
            "fiscal_years": [2023],
            "include_annual": False,
            "include_quarterly": True,
        },
        checks=["no_annual", "quarterly_count>=3", "fy2023_quarterly"],
    ),
    Scenario(
        name="jpm_latest_revenue",
        ticker="JPM",
        kwargs={},
        checks=["annual_count=1", "jpm_revenue_ok"],
    ),
    Scenario(
        name="bac_latest_revenue",
        ticker="BAC",
        kwargs={},
        checks=["annual_count=1", "has_revenue"],
    ),
]


def _run_check(result: StatementFetchResult, check: str, scenario: Scenario) -> tuple[bool, str]:
    scope = result.scope_applied
    annual_n = scope.get("annual_period_count", 0)
    quarterly_n = scope.get("quarterly_period_count", 0)

    if check == "annual_count=1":
        ok = annual_n == 1
        return ok, f"annual_period_count={annual_n} want 1"
    if check == "annual_count>=3":
        ok = annual_n >= 3
        return ok, f"annual_period_count={annual_n} want >=3"
    if check == "annual_count>=2":
        ok = annual_n >= 2
        return ok, f"annual_period_count={annual_n} want >=2"
    if check == "no_annual":
        ok = annual_n == 0
        return ok, f"annual_period_count={annual_n} want 0"
    if check == "no_quarterly":
        ok = quarterly_n == 0
        return ok, f"quarterly_period_count={quarterly_n} want 0"
    if check == "quarterly_count>=4":
        ok = quarterly_n >= 4
        return ok, f"quarterly_period_count={quarterly_n} want >=4"
    if check == "quarterly_count>=3":
        ok = quarterly_n >= 3
        return ok, f"quarterly_period_count={quarterly_n} want >=3"
    if check == "has_revenue":
        rev = _metric(result, "revenue")
        ok = rev is not None and rev > 0
        return ok, f"revenue={rev}"
    if check == "fy_included=2023":
        years = _annual_years(result)
        ok = 2023 in years
        return ok, f"fiscal_years_included={years}"
    if check == "fy2023_quarterly":
        labels = _quarterly_labels(result)
        ok = any("FY2023" in x for x in labels)
        return ok, f"quarterly={labels}"
    if check == "jpm_revenue_ok":
        rev = _metric(result, "revenue")
        ok = rev is not None and rev > 150e9
        return ok, f"revenue={rev/1e9:.2f}B want >150B"
    return False, f"unknown check {check}"


def run_scenarios(
    *,
    only: str | None = None,
    tickers_filter: str | None = None,
) -> int:
    ensure_edgar_identity()
    selected = SCENARIOS
    if only:
        selected = [s for s in SCENARIOS if s.name == only]
        if not selected:
            print(f"Unknown scenario: {only}")
            return 1

    passed = failed = 0
    print("homework.statement_fetch — scenario tests\n")

    for scenario in selected:
        if tickers_filter and scenario.ticker not in tickers_filter.split(","):
            continue
        print(f"▶ {scenario.name} ({scenario.ticker}) {scenario.kwargs or 'defaults'}")
        try:
            result = fetch_sec_financials(ticker=scenario.ticker, **scenario.kwargs)
        except Exception as exc:
            print(f"  FAIL fetch: {exc}")
            failed += 1
            continue

        scope = result.scope_applied
        rev = _metric(result, "revenue")
        ni = _metric(result, "net_income")
        print(
            f"  scope: annual={scope.get('annual_period_count')} "
            f"quarterly={scope.get('quarterly_period_count')} "
            f"fys={scope.get('fiscal_years_included')} "
            f"q_fys={scope.get('quarterly_fiscal_years_included')}"
        )
        if rev is not None:
            print(f"  latest revenue=${rev/1e9:.2f}B  net_income=${ni/1e9:.2f}B" if ni else f"  latest revenue=${rev/1e9:.2f}B")
        if result.warnings:
            print(f"  warnings: {result.warnings}")

        scenario_ok = True
        for check in scenario.checks:
            ok, msg = _run_check(result, check, scenario)
            mark = "✓" if ok else "✗"
            print(f"  {mark} {check}: {msg}")
            if not ok:
                scenario_ok = False
        if scenario_ok:
            passed += 1
        else:
            failed += 1
        print()

    print(f"Results: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Statement-based SEC fetch (homework)")
    parser.add_argument("--scenario", help="Run one scenario by name")
    parser.add_argument("--tickers", help="Filter scenarios by ticker")
    args = parser.parse_args()
    return run_scenarios(only=args.scenario, tickers_filter=args.tickers)


if __name__ == "__main__":
    sys.exit(main())
