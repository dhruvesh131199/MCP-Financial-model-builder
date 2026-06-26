"""Tests for detailed analysis extraction pickers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ingest.detailed_extract import (
    DETAILED_BALANCE_ORDER,
    DETAILED_CASHFLOW_ORDER,
    DETAILED_INCOME_ORDER,
    build_detailed_snapshot,
    extract_detailed_period,
)

FIXTURES = Path(__file__).resolve().parents[2] / "homework" / "hero_output"


def _fixture_dir(ticker: str) -> Path:
    matches = sorted(FIXTURES.glob(f"{ticker}_*"))
    if not matches:
        pytest.skip(f"fixture missing for {ticker} under {FIXTURES}")
    return matches[-1]


def _load_csv(ticker: str, name: str) -> pd.DataFrame:
    path = _fixture_dir(ticker) / name
    if not path.exists():
        pytest.skip(f"fixture missing: {path}")
    return pd.read_csv(path)


def _latest_col(df: pd.DataFrame) -> str:
    for col in df.columns:
        if col[0].isdigit():
            return col
    raise ValueError("no period column")


@pytest.fixture
def aapl_income() -> pd.DataFrame:
    return _load_csv("AAPL", "income_standard.csv")


@pytest.fixture
def aapl_balance() -> pd.DataFrame:
    return _load_csv("AAPL", "balance_standard.csv")


@pytest.fixture
def aapl_cashflow() -> pd.DataFrame:
    return _load_csv("AAPL", "cashflow_standard.csv")


@pytest.fixture
def jpm_cashflow() -> pd.DataFrame:
    return _load_csv("JPM", "cashflow_standard.csv")


@pytest.fixture
def gm_income() -> pd.DataFrame:
    return _load_csv("GM", "income_standard.csv")


@pytest.fixture
def gm_balance() -> pd.DataFrame:
    return _load_csv("GM", "balance_standard.csv")


@pytest.fixture
def gm_cashflow() -> pd.DataFrame:
    return _load_csv("GM", "cashflow_standard.csv")


@pytest.fixture
def cost_income() -> pd.DataFrame:
    return _load_csv("COST", "income_standard.csv")


@pytest.fixture
def cost_balance() -> pd.DataFrame:
    return _load_csv("COST", "balance_standard.csv")


@pytest.fixture
def cost_cashflow() -> pd.DataFrame:
    return _load_csv("COST", "cashflow_standard.csv")


def test_aapl_income_revenue_and_operating_cost(aapl_income: pd.DataFrame):
    col = _latest_col(aapl_income)
    period = extract_detailed_period(aapl_income, None, None, col, fy_end_mmdd="0930")
    assert period.income["revenue"].value == 416161000000.0
    assert period.income["cost_of_revenue"].value == 220960000000.0
    assert period.income["gross_profit"].value == 195201000000.0
    assert period.income["operating_cost"].value == 62151000000.0
    assert period.income["operating_income"].value == 133050000000.0
    assert period.income["net_income"].value == 112010000000.0
    assert "eps_diluted" in period.income
    eps = period.income["eps_diluted"]
    if eps.value is not None:
        assert eps.value > 0


def test_aapl_balance_section_totals(aapl_balance: pd.DataFrame):
    col = _latest_col(aapl_balance)
    period = extract_detailed_period(None, aapl_balance, None, col, fy_end_mmdd="0930")
    assert period.balance["current_assets"].value == 147957000000.0
    assert period.balance["non_current_assets"].value == 211284000000.0
    assert period.balance["total_assets"].value == 359241000000.0
    assert period.balance["current_liabilities"].value == 165631000000.0
    assert period.balance["non_current_liabilities"].value == 119877000000.0
    assert period.balance["total_liabilities"].value == 285508000000.0
    assert period.balance["stockholders_equity"].value == 73733000000.0
    assert period.accounting_equation_ok is True


def test_aapl_cashflow_sections_and_fcf(aapl_cashflow: pd.DataFrame):
    col = _latest_col(aapl_cashflow)
    period = extract_detailed_period(None, None, aapl_cashflow, col, fy_end_mmdd="0930")
    assert period.cashflow["operating_cash_flow"].value == 111482000000.0
    assert period.cashflow["investing_cash_flow"].value == 15195000000.0
    assert period.cashflow["financing_cash_flow"].value == -120686000000.0
    assert period.cashflow["net_cash_change"].value == 5991000000.0
    # OCF 111.482B - capex 12.715B
    assert period.cashflow["free_cash_flow"].value == pytest.approx(98767000000.0, rel=1e-4)


def test_jpm_investing_not_other_subline(jpm_cashflow: pd.DataFrame):
    col = _latest_col(jpm_cashflow)
    period = extract_detailed_period(None, None, jpm_cashflow, col, fy_end_mmdd="1231")
    assert period.cashflow["investing_cash_flow"].value == -265565000000.0
    assert period.cashflow["financing_cash_flow"].value == 269533000000.0
    assert period.cashflow["investing_cash_flow"].xbrl_tag == (
        "NetCashProvidedByUsedInInvestingActivities"
    )


def test_gm_conglomerate_cogs_and_derived_metrics(
    gm_income: pd.DataFrame,
    gm_balance: pd.DataFrame,
    gm_cashflow: pd.DataFrame,
):
    col = _latest_col(gm_income)
    period = extract_detailed_period(
        gm_income, gm_balance, gm_cashflow, col, fy_end_mmdd="1231"
    )
    assert period.income["cost_of_revenue"].value == pytest.approx(
        173423000000.0, rel=1e-4
    )
    assert period.income["cost_of_revenue"].xbrl_tag == "conglomerate_cogs_sum"
    assert period.income["gross_profit"].value == pytest.approx(
        11596000000.0, rel=1e-4
    )
    assert period.income["gross_profit"].source == "derived"
    assert period.income["operating_cost"].value == pytest.approx(
        8687000000.0, rel=1e-4
    )
    assert period.income["ebitda"].value == pytest.approx(17497000000.0, rel=1e-4)
    assert period.income["ebitda"].source == "derived"
    assert period.balance["cash_end_of_period"].value == pytest.approx(
        20945000000.0, rel=1e-4
    )
    assert period.accounting_equation_ok is True


def test_cost_derived_gross_profit_and_non_current(
    cost_income: pd.DataFrame,
    cost_balance: pd.DataFrame,
    cost_cashflow: pd.DataFrame,
):
    col = _latest_col(cost_income)
    period = extract_detailed_period(
        cost_income, cost_balance, cost_cashflow, col, fy_end_mmdd="0831"
    )
    assert period.income["gross_profit"].value == pytest.approx(
        35349000000.0, rel=1e-4
    )
    assert period.income["gross_profit"].source == "derived"
    assert period.income["operating_cost"].value == pytest.approx(
        24966000000.0, rel=1e-4
    )
    assert period.income["ebitda"].value == pytest.approx(12809000000.0, rel=1e-4)
    assert period.balance["non_current_assets"].value == pytest.approx(
        38719000000.0, rel=1e-4
    )
    assert period.balance["non_current_assets"].source == "derived"
    assert period.balance["cash_end_of_period"].value == pytest.approx(
        14161000000.0, rel=1e-4
    )
    assert period.accounting_equation_ok is True


def test_build_snapshot_five_years(
    aapl_income: pd.DataFrame,
    aapl_balance: pd.DataFrame,
    aapl_cashflow: pd.DataFrame,
):
    snap = build_detailed_snapshot(
        ticker="AAPL",
        entity_name="Apple Inc.",
        cik="0000320193",
        fetched_at="2026-01-01T00:00:00+00:00",
        source="test",
        income_df=aapl_income,
        balance_df=aapl_balance,
        cashflow_df=aapl_cashflow,
        fy_end_mmdd="0930",
        max_periods=5,
    )
    assert len(snap.periods) == 5
    for key in DETAILED_INCOME_ORDER:
        assert snap.periods[0].income.get(key) is not None
    for key in DETAILED_BALANCE_ORDER:
        assert snap.periods[0].balance.get(key) is not None
    for key in DETAILED_CASHFLOW_ORDER:
        assert snap.periods[0].cashflow.get(key) is not None
