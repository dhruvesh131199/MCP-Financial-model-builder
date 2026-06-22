"""Adapt edgartools stitched DataFrames to FinancialStatements schema."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from ingest.concept_map import LINE_LABELS, STATEMENT_METRIC_ORDER
from ingest.coverage import build_coverage_report
from ingest.edgar_concept_map import (
    CONCEPT_PRIORITY,
    canonical_key_from_raw,
    canonical_keys_for_statement,
    standard_concept_map_for_statement,
    tag_priority_rank,
)
from ingest.edgar_fetch import EdgarFetchResult
from ingest.metric_catalog import METRICS_BY_KEY
from ingest.normalize import (
    FinancialStatements,
    LineItem,
    StatementPeriod,
    StatementSlice,
)


def _period_columns(df: pd.DataFrame) -> list[str]:
    cols: list[str] = []
    for col in df.columns:
        text = str(col)
        if len(text) >= 10 and text[4] == "-" and text[:4].isdigit():
            cols.append(text)
    return sorted(cols, reverse=True)


def _fiscal_year(end: str) -> int:
    return int(end[:4])


def _fiscal_period(end: str, *, annual: bool) -> str:
    if annual:
        return "FY"
    month = int(end[5:7])
    if month <= 3:
        return "Q1"
    if month <= 6:
        return "Q2"
    if month <= 9:
        return "Q3"
    return "Q4"


def _is_valid_number(value: Any) -> bool:
    if value is None:
        return False
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    if pd.isna(value):
        return False
    return True


def _unit_for_metric(key: str) -> str:
    m = METRICS_BY_KEY.get(key)
    return m.unit if m else "USD"


def _value_from_concept_rows(
    std_df: pd.DataFrame,
    concept: str,
    period_col: str,
) -> tuple[float | None, pd.Series | None]:
    """Pick one XBRL row per standard_concept — never sum duplicate lines."""
    if period_col not in std_df.columns:
        return None, None
    rows = std_df[std_df["standard_concept"] == concept]
    if rows.empty:
        return None, None

    best_row: pd.Series | None = None
    best_rank = 10**9
    for _, row in rows.iterrows():
        val = row.get(period_col)
        if not _is_valid_number(val):
            continue
        rank = tag_priority_rank(concept, str(row.get("concept") or ""))
        if rank < best_rank:
            best_rank = rank
            best_row = row

    if best_row is None:
        return None, None
    return float(best_row[period_col]), best_row


def _concepts_for_key(key: str, statement: str) -> tuple[str, ...]:
    if key in CONCEPT_PRIORITY:
        return CONCEPT_PRIORITY[key]
    concept_map = standard_concept_map_for_statement(statement)
    return tuple(
        concept
        for concept, mapped in concept_map.items()
        if mapped == key
    )


def _extract_values_for_period(
    df: pd.DataFrame,
    period_col: str,
    statement: str,
) -> tuple[dict[str, float], dict[str, dict[str, str]]]:
    """Map one period column to canonical keys + provenance."""
    values: dict[str, float] = {}
    provenance: dict[str, dict[str, str]] = {}
    period_cols = [period_col]
    work = df.copy()
    for col in _period_columns(work):
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce")

    std_df = work[work["standard_concept"].notna()].copy()
    for col in period_cols:
        if col in std_df.columns:
            std_df[col] = pd.to_numeric(std_df[col], errors="coerce")
    if not std_df.empty and "standard_concept" in std_df.columns:
        keys = canonical_keys_for_statement(statement)
        for key in keys:
            if key in values:
                continue
            for concept in _concepts_for_key(key, statement):
                val, tag_row = _value_from_concept_rows(std_df, concept, period_col)
                if val is None:
                    continue
                values[key] = val
                provenance[key] = {
                    "xbrl_tag": _strip_tag(tag_row.get("concept")) if tag_row is not None else None,
                    "standard_concept": concept,
                }
                break

    if "concept" in work.columns:
        for _, row in work.iterrows():
            if row.get("standard_concept") is not None and not pd.isna(
                row.get("standard_concept")
            ):
                continue
            raw_key = canonical_key_from_raw(str(row.get("concept") or ""))
            if raw_key is None or raw_key in values:
                continue
            val = row.get(period_col)
            if not _is_valid_number(val):
                continue
            values[raw_key] = float(val)
            provenance[raw_key] = {
                "xbrl_tag": _strip_tag(row.get("concept")),
                "standard_concept": "",
            }

    return values, provenance


def _strip_tag(concept: Any) -> str | None:
    if concept is None or (isinstance(concept, float) and pd.isna(concept)):
        return None
    text = str(concept)
    for prefix in ("us-gaap_", "dei_", "srt_"):
        if text.startswith(prefix):
            return text[len(prefix) :]
    return text


def _dedupe_periods(periods: list[StatementPeriod]) -> list[StatementPeriod]:
    """Keep one row per period end (edgartools can map two columns to the same FY/Q)."""
    by_end: dict[str, StatementPeriod] = {}
    for period in periods:
        key = period.period_end or f"{period.fiscal_year}:{period.fiscal_period}"
        if key not in by_end:
            by_end[key] = period
    return sorted(
        by_end.values(),
        key=lambda p: (p.period_end or "", p.fiscal_year, p.fiscal_period),
        reverse=True,
    )


def _dataframe_to_periods(
    df: pd.DataFrame | None,
    statement: str,
    *,
    annual: bool,
) -> list[StatementPeriod]:
    if df is None or df.empty:
        return []

    order = STATEMENT_METRIC_ORDER.get(statement, ())
    periods: list[StatementPeriod] = []

    for period_col in _period_columns(df):
        values, prov = _extract_values_for_period(df, period_col, statement)
        if not values:
            continue

        ordered_keys = [k for k in order if k in values]
        extra_keys = [k for k in values if k not in ordered_keys]
        line_items = [
            LineItem(
                key=k,
                label=LINE_LABELS.get(k, k),
                value=values[k],
                unit=_unit_for_metric(k),
                source="xbrl",
                xbrl_tag=prov.get(k, {}).get("xbrl_tag"),
            )
            for k in ordered_keys + extra_keys
        ]
        period = StatementPeriod(
            fiscal_year=_fiscal_year(period_col),
            fiscal_period=_fiscal_period(period_col, annual=annual),
            period_end=str(period_col),
            filed=None,
            form="10-K" if annual else "10-Q",
            line_items=line_items,
        )
        periods.append(period)

    periods = _dedupe_periods(periods)
    periods.sort(
        key=lambda p: (p.period_end or "", p.fiscal_year, p.fiscal_period),
        reverse=True,
    )
    return periods


def adapt_edgar_to_financials(
    fetch: EdgarFetchResult,
    *,
    fetch_scope: list[str] | None = None,
    coverage_fiscal_year: int | None = None,
) -> FinancialStatements:
    """Convert EdgarFetchResult → FinancialStatements."""
    scope = fetch_scope or list(STATEMENT_METRIC_ORDER.keys())
    statements: dict[str, StatementSlice] = {}

    for stmt_key in scope:
        annual_df = fetch.frames.annual.get(stmt_key)
        quarterly_df = fetch.frames.quarterly.get(stmt_key)
        statements[stmt_key] = StatementSlice(
            annual=_dataframe_to_periods(annual_df, stmt_key, annual=True),
            quarterly=_dataframe_to_periods(quarterly_df, stmt_key, annual=False),
        )

    result = FinancialStatements(
        ticker=fetch.ticker,
        cik=fetch.cik,
        entity_name=fetch.entity_name,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        statements=statements,
        fetch_scope=scope,
        ingest_source="edgartools",
    )

    dump = result.model_dump()
    fy = coverage_fiscal_year
    if fy is None:
        income = statements.get("income")
        if income and income.annual:
            fy = income.annual[0].fiscal_year
    if fy is not None:
        cov = build_coverage_report(dump, fy)
        result = result.model_copy(update={"coverage": cov})

    return result
