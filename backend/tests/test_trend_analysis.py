"""Tests for trend analysis compute."""

from __future__ import annotations

import pytest

from engine.trend_analysis import build_trend_table
from ingest.detailed_extract import DetailedAnalysisSnapshot, DetailedPeriod, MetricCell


def _cell(key: str, value: float | None, source: str = "xbrl") -> MetricCell:
    return MetricCell(key=key, value=value, source=source)  # type: ignore[arg-type]


def _period(
    fy: int,
    *,
    revenue: float,
    gross_profit: float | None,
    operating_income: float,
    eps: float | None = None,
    bank: bool = False,
) -> DetailedPeriod:
    income: dict[str, MetricCell] = {
        "revenue": _cell("revenue", revenue),
        "operating_income": _cell("operating_income", operating_income),
    }
    if gross_profit is not None:
        income["gross_profit"] = _cell("gross_profit", gross_profit)
    else:
        income["gross_profit"] = MetricCell(key="gross_profit", source="n/a")
    if eps is not None:
        income["eps_diluted"] = _cell("eps_diluted", eps)
    return DetailedPeriod(
        fiscal_year=fy,
        fiscal_period="FY",
        period_end=f"{fy}-12-31",
        income=income,
        is_bank_style=bank,
    )


def test_trend_table_growth_and_margins():
    snapshot = DetailedAnalysisSnapshot(
        ticker="TST",
        entity_name="Test",
        cik="1",
        fetched_at="2026-01-01T00:00:00+00:00",
        source="test",
        periods=[
            _period(2025, revenue=110.0, gross_profit=55.0, operating_income=22.0, eps=2.2),
            _period(2024, revenue=100.0, gross_profit=50.0, operating_income=20.0, eps=2.0),
            _period(2023, revenue=90.0, gross_profit=45.0, operating_income=18.0, eps=1.8),
        ],
    )
    table = build_trend_table(snapshot, max_years=3)
    assert table.fiscal_years == [2025, 2024, 2023]

    by_key = {r.key: r for r in table.rows}
    assert by_key["revenue"].values == [110.0, 100.0, 90.0]
    assert by_key["revenue_growth_yoy"].values[0] == 10.0
    assert by_key["revenue_growth_yoy"].values[-1] is None
    assert by_key["gross_margin_pct"].values[0] == 50.0
    assert by_key["ebit_margin_pct"].values[0] == 20.0
    assert by_key["eps_growth_yoy"].values[0] == pytest.approx(10.0)
    assert by_key["revenue_growth_yoy"].highlight is True


def test_trend_bank_style_null_gross_margin():
    snapshot = DetailedAnalysisSnapshot(
        ticker="JPM",
        entity_name="JPM",
        cik="1",
        fetched_at="2026-01-01T00:00:00+00:00",
        source="test",
        periods=[
            _period(2025, revenue=100.0, gross_profit=None, operating_income=30.0, bank=True),
            _period(2024, revenue=90.0, gross_profit=None, operating_income=27.0, bank=True),
        ],
    )
    table = build_trend_table(snapshot)
    by_key = {r.key: r for r in table.rows}
    assert by_key["gross_margin_pct"].values == [None, None]
    assert by_key["ebit_margin_pct"].values[0] == 30.0


def test_eps_derived_from_net_income_and_shares():
    p = DetailedPeriod(
        fiscal_year=2025,
        fiscal_period="FY",
        period_end="2025-12-31",
        income={
            "revenue": _cell("revenue", 100.0),
            "gross_profit": _cell("gross_profit", 50.0),
            "operating_income": _cell("operating_income", 20.0),
            "net_income": _cell("net_income", 10.0),
            "weighted_avg_shares_diluted": _cell("weighted_avg_shares_diluted", 4.0),
        },
    )
    snapshot = DetailedAnalysisSnapshot(
        ticker="TST",
        entity_name="Test",
        cik="1",
        fetched_at="2026-01-01T00:00:00+00:00",
        source="test",
        periods=[p],
    )
    table = build_trend_table(snapshot)
    eps_row = next(r for r in table.rows if r.key == "eps_diluted")
    assert eps_row.values[0] == 2.5
