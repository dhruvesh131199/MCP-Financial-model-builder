"""Tests for edgartools DataFrame → FinancialStatements adapter."""

import pandas as pd

from ingest.edgar_adapter import _dataframe_to_periods, adapt_edgar_to_financials
from ingest.edgar_fetch import EdgarFetchResult, EdgarFrameSet


def _amd_income_fixture_df() -> pd.DataFrame:
    """Minimal stitched income DataFrame (object period cols like edgartools)."""
    return pd.DataFrame(
        {
            "label": ["Net revenue", "Net income"],
            "concept": [
                "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
                "us-gaap_NetIncomeLoss",
            ],
            "standard_concept": ["Revenue", "NetIncome"],
            "2025-12-27": [34639000000.0, 4335000000.0],
            "2024-12-28": [25785000000.0, 1641000000.0],
            "preferred_sign": [1, 1],
        }
    )


def test_dataframe_to_periods_maps_standard_concepts():
    periods = _dataframe_to_periods(_amd_income_fixture_df(), "income", annual=True)
    assert len(periods) == 2
    fy2025 = next(p for p in periods if p.fiscal_year == 2025)
    values = {li.key: li.value for li in fy2025.line_items}
    assert values["revenue"] == 34639000000.0
    assert values["net_income"] == 4335000000.0


def test_adapt_edgar_sets_ingest_source():
    fetch = EdgarFetchResult(
        ticker="AMD",
        cik="0000002488",
        entity_name="ADVANCED MICRO DEVICES INC",
        frames=EdgarFrameSet(annual={"income": _amd_income_fixture_df()}),
    )
    result = adapt_edgar_to_financials(fetch, fetch_scope=["income"])
    assert result.ingest_source == "edgartools"
    assert result.statements["income"].annual[0].fiscal_year == 2025


def test_amd_cost_of_revenue_picks_total_not_sum_of_duplicate_concepts():
    """AMD FY2023: two COGS lines share CostOfGoodsAndServicesSold — must not sum."""
    df = pd.DataFrame(
        {
            "label": ["Net revenue", "Cost of sales", "Total cost of sales", "Gross profit"],
            "concept": [
                "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
                "us-gaap_CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
                "us-gaap_CostOfGoodsAndServicesSold",
                "us-gaap_GrossProfit",
            ],
            "standard_concept": [
                "Revenue",
                "CostOfGoodsAndServicesSold",
                "CostOfGoodsAndServicesSold",
                "GrossProfit",
            ],
            "2023-12-30": [22680000000.0, 11278000000.0, 12220000000.0, 10460000000.0],
            "preferred_sign": [1, 1, 1, 1],
        }
    )
    periods = _dataframe_to_periods(df, "income", annual=True)
    fy2023 = next(p for p in periods if p.fiscal_year == 2023)
    values = {li.key: li for li in fy2023.line_items}
    assert values["cost_of_revenue"].value == 12220000000.0
    assert values["cost_of_revenue"].source == "xbrl"
    assert "ebitda" not in values


def test_adapt_edgar_no_derived_lines():
    income_df = pd.DataFrame(
        {
            "label": ["Operating income"],
            "concept": ["us-gaap_OperatingIncomeLoss"],
            "standard_concept": ["OperatingIncomeLoss"],
            "2025-12-27": [3694000000.0],
            "preferred_sign": [1],
        }
    )
    cashflow_df = pd.DataFrame(
        {
            "label": ["Depreciation and amortization"],
            "concept": ["us-gaap_DepreciationDepletionAndAmortization"],
            "standard_concept": ["DepreciationExpense"],
            "2025-12-27": [750000000.0],
            "preferred_sign": [1],
        }
    )
    fetch = EdgarFetchResult(
        ticker="AMD",
        cik="0000002488",
        entity_name="ADVANCED MICRO DEVICES INC",
        frames=EdgarFrameSet(
            annual={"income": income_df, "cashflow": cashflow_df},
        ),
    )
    result = adapt_edgar_to_financials(fetch, fetch_scope=["income", "cashflow"])
    income = result.statements["income"].annual[0]
    keys = {li.key for li in income.line_items}
    assert "ebitda" not in keys
    assert "depreciation_and_amortization" not in keys
    assert all(li.source == "xbrl" for li in income.line_items)
