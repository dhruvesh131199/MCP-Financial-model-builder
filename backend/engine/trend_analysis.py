"""Trend analysis table — revenue, margins, EPS, and YoY growth from detailed snapshot."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ingest.detailed_extract import DetailedAnalysisSnapshot, DetailedPeriod, MetricCell

RowType = Literal["currency", "percent", "eps"]


class TrendRow(BaseModel):
    key: str
    label: str
    row_type: RowType
    highlight: bool = False
    values: list[float | None] = Field(default_factory=list)


class TrendAnalysisTable(BaseModel):
    fiscal_years: list[int] = Field(default_factory=list)
    rows: list[TrendRow] = Field(default_factory=list)


def _cell_value(period: DetailedPeriod, key: str) -> float | None:
    cell = period.income.get(key)
    if cell is None or cell.source == "n/a":
        return None
    return cell.value


def _eps_for_period(period: DetailedPeriod) -> float | None:
    eps = _cell_value(period, "eps_diluted")
    if eps is not None:
        return eps
    ni = _cell_value(period, "net_income")
    shares = _cell_value(period, "weighted_avg_shares_diluted")
    if ni is not None and shares is not None and shares > 0:
        return ni / shares
    return None


def _safe_margin(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator * 100.0


def _yoy_growth(series: list[float | None]) -> list[float | None]:
    """YoY % for newest-first series; oldest column has no prior year."""
    out: list[float | None] = []
    for i in range(len(series)):
        if i >= len(series) - 1:
            out.append(None)
            continue
        cur, prev = series[i], series[i + 1]
        if cur is None or prev is None or prev == 0:
            out.append(None)
        else:
            out.append((cur - prev) / abs(prev) * 100.0)
    return out


def build_trend_table(
    snapshot: DetailedAnalysisSnapshot,
    *,
    max_years: int = 5,
) -> TrendAnalysisTable:
    periods = sorted(snapshot.periods, key=lambda p: p.fiscal_year, reverse=True)[
        :max_years
    ]
    if not periods:
        return TrendAnalysisTable()

    fiscal_years = [p.fiscal_year for p in periods]
    revenue = [_cell_value(p, "revenue") for p in periods]
    gross_profit = [_cell_value(p, "gross_profit") for p in periods]
    ebit = [_cell_value(p, "operating_income") for p in periods]
    eps = [_eps_for_period(p) for p in periods]

    gross_margin = [
        _safe_margin(gp, rev) for gp, rev in zip(gross_profit, revenue, strict=True)
    ]
    ebit_margin = [_safe_margin(e, rev) for e, rev in zip(ebit, revenue, strict=True)]

    rows = [
        TrendRow(
            key="revenue",
            label="Revenue",
            row_type="currency",
            highlight=False,
            values=revenue,
        ),
        TrendRow(
            key="revenue_growth_yoy",
            label="Revenue growth YoY %",
            row_type="percent",
            highlight=True,
            values=_yoy_growth(revenue),
        ),
        TrendRow(
            key="gross_profit",
            label="Gross profit",
            row_type="currency",
            highlight=False,
            values=gross_profit,
        ),
        TrendRow(
            key="gross_margin_pct",
            label="Gross margin %",
            row_type="percent",
            highlight=True,
            values=gross_margin,
        ),
        TrendRow(
            key="operating_income",
            label="EBIT",
            row_type="currency",
            highlight=False,
            values=ebit,
        ),
        TrendRow(
            key="ebit_margin_pct",
            label="EBIT margin %",
            row_type="percent",
            highlight=True,
            values=ebit_margin,
        ),
        TrendRow(
            key="eps_diluted",
            label="EPS",
            row_type="eps",
            highlight=False,
            values=eps,
        ),
        TrendRow(
            key="eps_growth_yoy",
            label="EPS growth YoY %",
            row_type="percent",
            highlight=True,
            values=_yoy_growth(eps),
        ),
    ]
    return TrendAnalysisTable(fiscal_years=fiscal_years, rows=rows)


def trend_to_dict(table: TrendAnalysisTable) -> dict[str, Any]:
    return table.model_dump()
