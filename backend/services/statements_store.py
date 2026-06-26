"""Hierarchical statements cache: ticker → period → statement leaf."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ingest.normalize import FinancialStatements, LineItem, StatementPeriod, StatementSlice
from ingest.statements_cache import (
    PeriodCache,
    StatementLeaf,
    StatementType,
    StatementsIndex,
    TickerCache,
    period_key,
)
from store import load_statements_index_raw, save_statements_index_raw

ALL_STATEMENTS: tuple[StatementType, ...] = ("income", "balance", "cashflow")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_index(session_id: str) -> StatementsIndex:
    raw = load_statements_index_raw(session_id)
    if not raw:
        return StatementsIndex()
    return StatementsIndex.model_validate(raw)


def save_index(session_id: str, index: StatementsIndex) -> None:
    index.updated_at = _utc_now()
    save_statements_index_raw(session_id, index.model_dump())


def _ticker_bucket(index: StatementsIndex, ticker: str) -> TickerCache | None:
    return index.tickers.get(ticker.upper())


def has_ticker(session_id: str, ticker: str) -> bool:
    index = load_index(session_id)
    bucket = _ticker_bucket(index, ticker)
    return bool(bucket and bucket.periods)


def cache_has_quarterly(session_id: str, ticker: str) -> bool:
    bucket = _ticker_bucket(load_index(session_id), ticker)
    if not bucket:
        return False
    for period in bucket.periods.values():
        if period.fiscal_period.upper().startswith("Q") and period.statements:
            return True
    return False


def has_period(session_id: str, ticker: str, period_key_str: str) -> bool:
    bucket = _ticker_bucket(load_index(session_id), ticker)
    if not bucket:
        return False
    period = bucket.periods.get(period_key_str)
    return bool(period and period.statements)


def has_statement(
    session_id: str,
    ticker: str,
    period_key_str: str,
    statement: StatementType,
) -> bool:
    bucket = _ticker_bucket(load_index(session_id), ticker)
    if not bucket:
        return False
    period = bucket.periods.get(period_key_str)
    if not period:
        return False
    leaf = period.statements.get(statement)
    return bool(leaf and leaf.line_items)


@dataclass
class FetchGap:
    ticker: str
    period_key: str
    statement: StatementType
    fiscal_year: int
    fiscal_period: str


def _annual_period_keys_from_cache(bucket: TickerCache) -> list[str]:
    keys: list[tuple[int, str]] = []
    for key, period in bucket.periods.items():
        if period.fiscal_period.upper().startswith("Q"):
            continue
        keys.append((period.fiscal_year, key))
    keys.sort(reverse=True)
    return [k for _, k in keys]


def _required_annual_keys(
    *,
    bucket: TickerCache | None,
    fiscal_years: list[int] | None,
    max_years: int,
) -> list[tuple[str, int, str]]:
    """Return list of (period_key, fiscal_year, fiscal_period)."""
    if fiscal_years:
        return [(period_key(y, "FY"), y, "FY") for y in sorted(fiscal_years, reverse=True)]

    anchor_year: int | None = None
    if bucket and bucket.periods:
        annual = [
            p.fiscal_year
            for p in bucket.periods.values()
            if not p.fiscal_period.upper().startswith("Q")
        ]
        if annual:
            anchor_year = max(annual)

    if anchor_year is None:
        anchor_year = datetime.now(timezone.utc).year

    out: list[tuple[str, int, str]] = []
    for i in range(max_years):
        fy = anchor_year - i
        out.append((period_key(fy, "FY"), fy, "FY"))
    return out


def compute_fetch_gaps(
    session_id: str,
    ticker: str,
    *,
    fiscal_years: list[int] | None = None,
    max_years: int = 1,
    include_annual: bool = True,
    include_quarterly: bool = False,
    statements: list[str] | None = None,
) -> list[FetchGap]:
    sym = ticker.upper()
    stmt_list: list[StatementType] = [
        s for s in (statements or list(ALL_STATEMENTS)) if s in ALL_STATEMENTS
    ]
    if not stmt_list:
        stmt_list = list(ALL_STATEMENTS)

    index = load_index(session_id)
    bucket = _ticker_bucket(index, sym)

    gaps: list[FetchGap] = []

    if include_annual:
        required = _required_annual_keys(
            bucket=bucket,
            fiscal_years=fiscal_years,
            max_years=max_years,
        )
        for pk, fy, fp in required:
            for stmt in stmt_list:
                if not has_statement(session_id, sym, pk, stmt):
                    gaps.append(
                        FetchGap(
                            ticker=sym,
                            period_key=pk,
                            statement=stmt,
                            fiscal_year=fy,
                            fiscal_period=fp,
                        )
                    )

    if include_quarterly and bucket:
        for pk, period in bucket.periods.items():
            if not period.fiscal_period.upper().startswith("Q"):
                continue
            for stmt in stmt_list:
                if not has_statement(session_id, sym, pk, stmt):
                    gaps.append(
                        FetchGap(
                            ticker=sym,
                            period_key=pk,
                            statement=stmt,
                            fiscal_year=period.fiscal_year,
                            fiscal_period=period.fiscal_period,
                        )
                    )

    return gaps


def gaps_grouped_by_statement(gaps: list[FetchGap]) -> dict[StatementType, list[FetchGap]]:
    grouped: dict[StatementType, list[FetchGap]] = {s: [] for s in ALL_STATEMENTS}
    for gap in gaps:
        grouped[gap.statement].append(gap)
    return {k: v for k, v in grouped.items() if v}


def merge_period_statement(
    session_id: str,
    ticker: str,
    *,
    period_meta: dict[str, Any],
    statement_type: StatementType,
    line_items: list[LineItem],
    fetch_meta: dict[str, Any],
    ticker_meta: dict[str, Any] | None = None,
) -> None:
    sym = ticker.upper()
    index = load_index(session_id)
    bucket = index.tickers.get(sym)
    if bucket is None:
        meta = ticker_meta or {}
        bucket = TickerCache(
            ticker=sym,
            cik=meta.get("cik"),
            entity_name=meta.get("entity_name"),
            fy_end_mmdd=meta.get("fy_end_mmdd"),
        )
        index.tickers[sym] = bucket

    if ticker_meta:
        if ticker_meta.get("cik"):
            bucket.cik = ticker_meta["cik"]
        if ticker_meta.get("entity_name"):
            bucket.entity_name = ticker_meta["entity_name"]
        if ticker_meta.get("fy_end_mmdd"):
            bucket.fy_end_mmdd = ticker_meta["fy_end_mmdd"]

    fy = int(period_meta["fiscal_year"])
    fp = str(period_meta.get("fiscal_period") or "FY")
    pk = period_key(fy, fp)

    period = bucket.periods.get(pk)
    if period is None:
        period = PeriodCache(
            fiscal_year=fy,
            fiscal_period=fp,
            period_end=period_meta.get("period_end"),
            filed=period_meta.get("filed"),
            form=period_meta.get("form"),
        )
        bucket.periods[pk] = period
    else:
        if period_meta.get("period_end"):
            period.period_end = period_meta["period_end"]
        if period_meta.get("filed"):
            period.filed = period_meta["filed"]
        if period_meta.get("form"):
            period.form = period_meta["form"]

    period.statements[statement_type] = StatementLeaf(
        line_items=line_items,
        fetched_at=fetch_meta.get("fetched_at") or _utc_now(),
        ingest_source=fetch_meta.get("ingest_source"),
        dedup_key=fetch_meta.get("dedup_key"),
    )
    bucket.updated_at = _utc_now()
    save_index(session_id, index)


def sync_financials_to_cache(
    session_id: str,
    financials: FinancialStatements,
    *,
    statements_written: list[str] | None = None,
    dedup_key: str | None = None,
) -> None:
    """Write each statement period from FinancialStatements into the hierarchical cache."""
    sym = financials.ticker.upper()
    ticker_meta = {
        "cik": financials.cik,
        "entity_name": financials.entity_name,
    }
    fetch_meta = {
        "fetched_at": financials.fetched_at,
        "ingest_source": financials.ingest_source,
        "dedup_key": dedup_key,
    }
    scope = statements_written or list(financials.fetch_scope or ALL_STATEMENTS)

    for stmt_key in scope:
        if stmt_key not in ALL_STATEMENTS:
            continue
        slice_ = financials.statements.get(stmt_key)
        if not slice_:
            continue
        for period in slice_.annual:
            merge_period_statement(
                session_id,
                sym,
                period_meta=period.model_dump(),
                statement_type=stmt_key,  # type: ignore[arg-type]
                line_items=period.line_items,
                fetch_meta=fetch_meta,
                ticker_meta=ticker_meta,
            )
        for period in slice_.quarterly:
            merge_period_statement(
                session_id,
                sym,
                period_meta=period.model_dump(),
                statement_type=stmt_key,  # type: ignore[arg-type]
                line_items=period.line_items,
                fetch_meta=fetch_meta,
                ticker_meta=ticker_meta,
            )


def _merge_period_line_items(
    bucket: TickerCache,
    pk: str,
    *,
    fiscal_year: int,
    fiscal_period: str,
) -> StatementPeriod:
    period = bucket.periods.get(pk)
    if not period:
        return StatementPeriod(
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            line_items=[],
        )
    merged: dict[str, LineItem] = {}
    order: list[str] = []
    for stmt in ALL_STATEMENTS:
        leaf = period.statements.get(stmt)
        if not leaf:
            continue
        for li in leaf.line_items:
            if li.key not in merged:
                order.append(li.key)
            merged[li.key] = li
    return StatementPeriod(
        fiscal_year=period.fiscal_year,
        fiscal_period=period.fiscal_period,
        period_end=period.period_end,
        filed=period.filed,
        form=period.form,
        line_items=[merged[k] for k in order],
    )


def materialize_financial_statements(
    session_id: str,
    ticker: str,
    *,
    fiscal_years: list[int] | None = None,
    max_years: int = 5,
    include_annual: bool = True,
    include_quarterly: bool = False,
    statements: list[str] | None = None,
) -> FinancialStatements | None:
    sym = ticker.upper()
    bucket = _ticker_bucket(load_index(session_id), sym)
    if not bucket:
        return None

    stmt_list = [s for s in (statements or list(ALL_STATEMENTS)) if s in ALL_STATEMENTS]
    if not stmt_list:
        stmt_list = list(ALL_STATEMENTS)

    if fiscal_years:
        allowed_annual = set(fiscal_years)
    else:
        annual_keys = _annual_period_keys_from_cache(bucket)
        allowed_annual = set(
            bucket.periods[pk].fiscal_year
            for pk in annual_keys[:max_years]
            if pk in bucket.periods
        )

    slices: dict[str, StatementSlice] = {}
    for stmt in stmt_list:
        annual: list[StatementPeriod] = []
        quarterly: list[StatementPeriod] = []
        for pk, period in bucket.periods.items():
            if stmt not in period.statements:
                continue
            if period.fiscal_period.upper().startswith("Q"):
                if include_quarterly:
                    if fiscal_years and period.fiscal_year not in fiscal_years:
                        continue
                    sp = _merge_period_line_items(
                        bucket,
                        pk,
                        fiscal_year=period.fiscal_year,
                        fiscal_period=period.fiscal_period,
                    )
                    leaf = period.statements[stmt]
                    sp = StatementPeriod(
                        fiscal_year=period.fiscal_year,
                        fiscal_period=period.fiscal_period,
                        period_end=period.period_end,
                        filed=period.filed,
                        form=period.form,
                        line_items=leaf.line_items,
                    )
                    quarterly.append(sp)
            else:
                if not include_annual:
                    continue
                if period.fiscal_year not in allowed_annual:
                    continue
                leaf = period.statements[stmt]
                annual.append(
                    StatementPeriod(
                        fiscal_year=period.fiscal_year,
                        fiscal_period=period.fiscal_period,
                        period_end=period.period_end,
                        filed=period.filed,
                        form=period.form,
                        line_items=list(leaf.line_items),
                    )
                )
        annual.sort(key=lambda p: p.fiscal_year, reverse=True)
        quarterly.sort(
            key=lambda p: (p.period_end or "", p.fiscal_year),
            reverse=True,
        )
        if not fiscal_years:
            annual = annual[:max_years]
        slices[stmt] = StatementSlice(annual=annual, quarterly=quarterly)

    latest_fetch = bucket.updated_at or _utc_now()
    return FinancialStatements(
        ticker=sym,
        cik=bucket.cik or "",
        entity_name=bucket.entity_name or sym,
        fetched_at=latest_fetch,
        statements=slices,
        fetch_scope=stmt_list,
        ingest_source="cache",
    )


def get_cached_periods_summary(session_id: str, ticker: str) -> dict[str, Any]:
    sym = ticker.upper()
    bucket = _ticker_bucket(load_index(session_id), sym)
    if not bucket:
        return {"cached_periods": [], "statements_by_period": {}}
    by_period: dict[str, list[str]] = {}
    for pk, period in bucket.periods.items():
        by_period[pk] = sorted(period.statements.keys())
    return {
        "cached_periods": sorted(bucket.periods.keys(), reverse=True),
        "statements_by_period": by_period,
    }
