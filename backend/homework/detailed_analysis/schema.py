"""Pydantic models for detailed analysis JSON export."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from engine.trend_analysis import TrendAnalysisTable
from ingest.detailed_extract import (
    BALANCE_GROUP_LABELS,
    DETAILED_BALANCE_ORDER,
    DETAILED_CASHFLOW_ORDER,
    DETAILED_INCOME_ORDER,
    DETAILED_LABELS,
    DetailedAnalysisSnapshot,
    DetailedPeriod,
    MetricCell,
)


class MetricCellOut(BaseModel):
    key: str
    label: str
    value: float | None = None
    xbrl_tag: str | None = None
    row_label: str | None = None
    source_statement: str | None = None
    source: Literal["xbrl", "derived", "n/a"] = "xbrl"
    warning: str | None = None
    group: str | None = None


class PeriodOut(BaseModel):
    fiscal_year: int
    fiscal_period: str
    period_end: str
    income: list[MetricCellOut] = Field(default_factory=list)
    balance: list[MetricCellOut] = Field(default_factory=list)
    cashflow: list[MetricCellOut] = Field(default_factory=list)
    is_bank_style: bool = False
    accounting_equation_ok: bool | None = None


class DetailedAnalysisOut(BaseModel):
    ticker: str
    entity_name: str
    cik: str
    fetched_at: str
    source: str
    periods: list[PeriodOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    integrity_checks: list[str] = Field(default_factory=list)
    is_bank_style: bool = False
    trend_analysis: TrendAnalysisTable | None = None


def _cell_out(cell: MetricCell, *, group: str | None = None) -> MetricCellOut:
    return MetricCellOut(
        key=cell.key,
        label=DETAILED_LABELS.get(cell.key, cell.key),
        value=cell.value,
        xbrl_tag=cell.xbrl_tag,
        row_label=cell.label,
        source_statement=cell.source_statement,
        source=cell.source,
        warning=cell.warning,
        group=group,
    )


def snapshot_to_output(snapshot: DetailedAnalysisSnapshot) -> DetailedAnalysisOut:
    periods_out: list[PeriodOut] = []
    for period in snapshot.periods:
        income = [
            _cell_out(period.income[k])
            for k in DETAILED_INCOME_ORDER
            if k in period.income
        ]
        balance = [
            _cell_out(period.balance[k], group=BALANCE_GROUP_LABELS.get(k))
            for k in DETAILED_BALANCE_ORDER
            if k in period.balance
        ]
        cashflow = [
            _cell_out(period.cashflow[k])
            for k in DETAILED_CASHFLOW_ORDER
            if k in period.cashflow
        ]
        periods_out.append(
            PeriodOut(
                fiscal_year=period.fiscal_year,
                fiscal_period=period.fiscal_period,
                period_end=period.period_end,
                income=income,
                balance=balance,
                cashflow=cashflow,
                is_bank_style=period.is_bank_style,
                accounting_equation_ok=period.accounting_equation_ok,
            )
        )
    return DetailedAnalysisOut(
        ticker=snapshot.ticker,
        entity_name=snapshot.entity_name,
        cik=snapshot.cik,
        fetched_at=snapshot.fetched_at,
        source=snapshot.source,
        periods=periods_out,
        warnings=snapshot.warnings,
        integrity_checks=snapshot.integrity_checks,
        is_bank_style=snapshot.is_bank_style,
    )


def snapshot_to_dict(snapshot: DetailedAnalysisSnapshot) -> dict[str, Any]:
    return snapshot_to_output(snapshot).model_dump()
