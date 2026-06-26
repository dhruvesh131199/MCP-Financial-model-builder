"""Tests for statement DataFrame metric extraction."""

import pandas as pd

from ingest.statement_extract import extract_statement_metrics, period_columns, smart_revenue


def _amd_income_fixture_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "label": ["Net revenue", "Net income"],
            "concept": [
                "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
                "us-gaap_NetIncomeLoss",
            ],
            "standard_concept": ["Revenue", "NetIncome"],
            "2025-12-27 (FY)": [34639000000.0, 4335000000.0],
            "2024-12-28 (FY)": [25785000000.0, 1641000000.0],
        }
    )


def test_extract_revenue_and_net_income():
    df = _amd_income_fixture_df()
    for col in period_columns(df):
        metrics = extract_statement_metrics(df, col, "income")
        if "2025" in col:
            assert metrics["revenue"]["value"] == 34639000000.0
            assert metrics["net_income"]["value"] == 4335000000.0


def test_amd_cost_of_revenue_picks_total_not_sub_line():
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
            "2023-12-30 (FY)": [22680000000.0, 11278000000.0, 12220000000.0, 10460000000.0],
        }
    )
    metrics = extract_statement_metrics(df, "2023-12-30 (FY)", "income")
    assert metrics["cost_of_revenue"]["value"] == 12220000000.0
    assert "ebitda" not in metrics


def test_jpm_total_revenue_not_principal_transactions():
    df = pd.DataFrame(
        {
            "label": ["Principal transactions", "Total net revenue"],
            "concept": [
                "us-gaap_PrincipalTransactionsRevenue",
                "us-gaap_RevenuesNetOfInterestExpense",
            ],
            "standard_concept": ["Revenue", None],
            "2025-12-31 (FY)": [27210000000.0, 182450000000.0],
        }
    )
    val, tag = smart_revenue(df, "2025-12-31 (FY)")
    assert val == 182450000000.0
    assert tag == "RevenuesNetOfInterestExpense"


def test_gm_total_net_sales_and_revenue_not_automotive_segment():
    """GM: automotive segment is RevenueFromContract; total is us-gaap_Revenues."""
    df = pd.DataFrame(
        {
            "label": [
                "Automotive",
                "GM Financial",
                "Total net sales and revenue (Note 3)",
            ],
            "concept": [
                "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
                "us-gaap_RevenueNotFromContractWithCustomer",
                "us-gaap_Revenues",
            ],
            "standard_concept": [None, None, None],
            "2025-12-31 (FY)": [167971000000.0, 17048000000.0, 185019000000.0],
        }
    )
    val, tag = smart_revenue(df, "2025-12-31 (FY)")
    assert val == 185019000000.0
    assert tag == "Revenues"


def test_no_derived_ebitda_from_cashflow_depreciation():
    income_df = pd.DataFrame(
        {
            "label": ["Operating income"],
            "concept": ["us-gaap_OperatingIncomeLoss"],
            "standard_concept": ["OperatingIncomeLoss"],
            "2025-12-27 (FY)": [3694000000.0],
        }
    )
    cashflow_df = pd.DataFrame(
        {
            "label": ["Depreciation and amortization"],
            "concept": ["us-gaap_DepreciationDepletionAndAmortization"],
            "standard_concept": ["DepreciationExpense"],
            "2025-12-27 (FY)": [750000000.0],
        }
    )
    income = extract_statement_metrics(income_df, "2025-12-27 (FY)", "income")
    cashflow = extract_statement_metrics(cashflow_df, "2025-12-27 (FY)", "cashflow")
    assert "ebitda" not in income
    assert "depreciation_and_amortization" in cashflow
