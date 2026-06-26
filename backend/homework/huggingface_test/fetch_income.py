"""Fetch latest annual income statement from edgartools (ground-truth source)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pandas as pd
from edgar import Company
from edgar.financials import Financials

from ingest.fiscal_calendar import fiscal_year_from_period_end
from ingest.statement_extract import period_columns, smart_revenue, statement_to_dataframe

PERIOD_COL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


@dataclass
class IncomeBaseline:
    ticker: str
    entity_name: str
    cik: str
    fiscal_year: int | None
    period_end: str | None
    filing_date: str | None
    accession_no: str | None
    rows: list[dict[str, Any]]
    period_columns: list[str]
    latest_period_col: str | None
    smart_revenue_usd: float | None
    smart_revenue_tag: str | None
    table_text: str
    line_items: list[dict[str, Any]]


def line_items_for_model(baseline: IncomeBaseline) -> list[dict[str, Any]]:
    """label + concept + value for latest FY — skips abstract / null amounts."""
    col = baseline.latest_period_col
    if not col:
        return []
    items: list[dict[str, Any]] = []
    for row in baseline.rows:
        if row.get("abstract") in (1, True, "1"):
            continue
        val = row.get(col)
        if val is None:
            continue
        label = row.get("label")
        concept = row.get("concept")
        if not label and not concept:
            continue
        items.append(
            {
                "label": str(label or ""),
                "concept": str(concept or ""),
                "value": val,
            }
        )
    return items


def _company_fy_end(company: Company) -> str | None:
    for source in (company, getattr(company, "data", None)):
        if source is None:
            continue
        fy = getattr(source, "fiscal_year_end", None)
        if fy:
            return str(fy)
    return None


def _latest_annual_col(df: pd.DataFrame) -> str | None:
    cols = period_columns(df)
    if not cols:
        return None
    for col in cols:
        if "(FY)" in str(col).upper() or "FY" in str(col).upper():
            return col
    return cols[0]


def _df_to_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        rec: dict[str, Any] = {}
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                rec[str(col)] = None
            elif isinstance(val, (int, float)):
                rec[str(col)] = float(val) if isinstance(val, float) else int(val)
            else:
                rec[str(col)] = str(val)
        rows.append(rec)
    return rows


def dataframe_to_markdown_table(
    df: pd.DataFrame,
    *,
    period_col: str,
    max_rows: int | None = None,
) -> str:
    """Compact markdown table for LLM prompt (label + latest period only)."""
    subset = df[["label", "concept", "standard_concept", period_col]].copy()
    if max_rows:
        subset = subset.head(max_rows)
    lines = [
        "| label | concept | standard_concept | amount_usd |",
        "| --- | --- | --- | --- |",
    ]
    for _, row in subset.iterrows():
        label = str(row.get("label") or "").replace("|", "/")
        concept = str(row.get("concept") or "").replace("|", "/")
        sc = str(row.get("standard_concept") or "").replace("|", "/")
        val = row.get(period_col)
        amount = "—" if val is None or (isinstance(val, float) and pd.isna(val)) else str(val)
        lines.append(f"| {label} | {concept} | {sc} | {amount} |")
    return "\n".join(lines)


def fetch_latest_income_baseline(ticker: str) -> IncomeBaseline:
    sym = ticker.strip().upper()
    company = Company(sym)
    entity_name = str(getattr(company, "name", sym) or sym)
    cik = str(getattr(company, "cik", "") or "")
    fy_end = _company_fy_end(company)

    filing = company.get_filings(form="10-K", amendments=False).latest()
    if filing is None:
        raise ValueError(f"No 10-K found for {sym}")

    fin = Financials.extract(filing)
    rendered = fin.income_statement(view="standard")
    df = statement_to_dataframe(rendered, view="standard")
    if df is None or df.empty:
        raise ValueError(f"Empty income statement for {sym}")

    latest_col = _latest_annual_col(df)
    period_end = str(latest_col).split("(")[0].strip() if latest_col else None
    fiscal_year = (
        fiscal_year_from_period_end(period_end, fy_end_mmdd=fy_end)
        if period_end
        else None
    )

    rev_usd, rev_tag = None, None
    if latest_col:
        rev_usd, rev_tag = smart_revenue(df, latest_col)

    period_cols = period_columns(df)
    table_text = (
        dataframe_to_markdown_table(df, period_col=latest_col)
        if latest_col
        else ""
    )
    full_rows = _df_to_rows(df)

    baseline = IncomeBaseline(
        ticker=sym,
        entity_name=entity_name,
        cik=cik,
        fiscal_year=fiscal_year,
        period_end=period_end,
        filing_date=str(getattr(filing, "filing_date", ""))[:10] or None,
        accession_no=str(getattr(filing, "accession_no", "")) or None,
        rows=full_rows,
        period_columns=period_cols,
        latest_period_col=latest_col,
        smart_revenue_usd=rev_usd,
        smart_revenue_tag=rev_tag,
        table_text=table_text,
        line_items=[],
    )
    baseline.line_items = line_items_for_model(baseline)
    return baseline


def baseline_to_dict(baseline: IncomeBaseline) -> dict[str, Any]:
    return {
        "ticker": baseline.ticker,
        "entity_name": baseline.entity_name,
        "cik": baseline.cik,
        "fiscal_year": baseline.fiscal_year,
        "period_end": baseline.period_end,
        "filing_date": baseline.filing_date,
        "accession_no": baseline.accession_no,
        "latest_period_col": baseline.latest_period_col,
        "period_columns": baseline.period_columns,
        "smart_revenue_usd": baseline.smart_revenue_usd,
        "smart_revenue_tag": baseline.smart_revenue_tag,
        "line_items": baseline.line_items,
        "rows": baseline.rows,
        "table_text": baseline.table_text,
    }
