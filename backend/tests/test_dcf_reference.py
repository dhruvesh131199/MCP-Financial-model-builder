"""Tests for DCF reference history (always 5Y, independent of projection years)."""

from engine.dcf_reference import (
    MAX_REFERENCE_YEARS,
    _ebitda_from_items,
    build_dcf_reference_history,
)


def _financials_fixture() -> dict:
    years = [2024, 2023, 2022, 2021, 2020, 2019]
    annual = []
    for i, fy in enumerate(years):
        rev = 100_000_000_000 * (1.1 ** (len(years) - 1 - i))
        annual.append(
            {
                "fiscal_year": fy,
                "form": "10-K",
                "line_items": [
                    {"key": "revenue", "value": rev},
                    {"key": "operating_income", "value": rev * 0.08},
                    {"key": "depreciation_and_amortization", "value": rev * 0.02},
                    {"key": "accounts_receivable", "value": rev * 0.11},
                    {"key": "inventory", "value": rev * 0.08},
                    {"key": "accounts_payable", "value": rev * 0.07},
                    {"key": "total_assets", "value": rev * 2},
                    {"key": "short_term_debt", "value": rev * 0.05},
                    {"key": "long_term_debt", "value": rev * 0.15},
                    {"key": "cash", "value": rev * 0.02},
                    {"key": "capex", "value": -rev * 0.05},
                    {"key": "free_cash_flow", "value": rev * 0.15},
                    {"key": "income_before_tax", "value": rev * 0.25},
                    {"key": "income_tax_expense", "value": rev * 0.05},
                ],
            }
        )
    return {
        "ticker": "MU",
        "entity_name": "Micron Technology",
        "statements": {
            "income": {"annual": annual, "quarterly": []},
            "balance": {"annual": annual, "quarterly": []},
        },
    }


def test_ebitda_derived_from_op_plus_da():
    items = {
        "operating_income": 80.0,
        "depreciation_and_amortization": 20.0,
    }
    assert _ebitda_from_items(items) == 100.0


def test_ebitda_not_invented_without_da():
    items = {"operating_income": 80.0}
    assert _ebitda_from_items(items) is None


def test_reference_always_caps_at_five_years():
    ref = build_dcf_reference_history(_financials_fixture(), max_years=MAX_REFERENCE_YEARS)
    assert len(ref.fiscal_years) == 5
    assert ref.fiscal_years == [2024, 2023, 2022, 2021, 2020]
    assert ref.ticker == "MU"
    assert ref.latest_revenue_usd is not None


def test_reference_rows_include_net_debt_and_ebitda():
    ref = build_dcf_reference_history(_financials_fixture())
    keys = {row.key for row in ref.rows}
    assert "net_debt" in keys
    assert "ebitda_margin" in keys
    assert "operating_margin" in keys
    assert "da_pct" in keys
    assert "ebit_m" in keys
    assert "nwc_pct" in keys
    ebitda_row = next(r for r in ref.rows if r.key == "ebitda_margin")
    assert all(v is not None for v in ebitda_row.values)


def test_reference_revenue_in_millions():
    ref = build_dcf_reference_history(_financials_fixture())
    rev_row = next(r for r in ref.rows if r.key == "revenue")
    assert rev_row.format == "currency_m"
    assert rev_row.values[0] is not None
    assert rev_row.values[0] > 1000  # billions → thousands of $M


def test_reference_independent_of_projection_years():
    ref = build_dcf_reference_history(_financials_fixture())
    projection_years = 3
    assert len(ref.fiscal_years) == 5
    assert projection_years != len(ref.fiscal_years)
