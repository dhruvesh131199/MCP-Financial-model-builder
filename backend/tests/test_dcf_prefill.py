"""Tests for DCF input prefill from SEC financials."""

import pytest

from engine.dcf_prefill import dcf_still_required, suggest_dcf_inputs
from ingest.normalize import FinancialStatements, LineItem, StatementPeriod, StatementSlice


def _sample_financials() -> FinancialStatements:
    period = StatementPeriod(
        fiscal_year=2025,
        fiscal_period="FY",
        line_items=[
            LineItem(key="revenue", label="Revenue", value=10_000_000_000.0),
            LineItem(key="net_income", label="Net Income", value=1_000_000_000.0),
            LineItem(key="ebitda", label="EBITDA", value=2_000_000_000.0),
            LineItem(
                key="depreciation_and_amortization",
                label="D&A",
                value=400_000_000.0,
            ),
            LineItem(key="income_before_tax", label="IBT", value=1_200_000_000.0),
            LineItem(key="income_tax_expense", label="Tax", value=200_000_000.0),
            LineItem(key="capex", label="Capex", value=500_000_000.0),
            LineItem(key="cash", label="Cash", value=2_000_000_000.0),
            LineItem(key="long_term_debt", label="LTD", value=3_000_000_000.0),
            LineItem(key="weighted_avg_shares_diluted", label="Shares", value=1_000_000_000.0),
        ],
    )
    prior = StatementPeriod(
        fiscal_year=2024,
        fiscal_period="FY",
        line_items=[
            LineItem(key="revenue", label="Revenue", value=8_000_000_000.0),
        ],
    )
    return FinancialStatements(
        ticker="TEST",
        cik="0000000001",
        entity_name="Test Corp",
        fetched_at="2026-01-01T00:00:00+00:00",
        statements={
            "income": StatementSlice(annual=[period, prior]),
            "balance": StatementSlice(),
            "cashflow": StatementSlice(),
        },
        ingest_source="edgartools",
    )


def test_suggest_dcf_inputs_millions_and_rates():
    fin = _sample_financials()
    suggested = suggest_dcf_inputs(fin)
    assert suggested["base_revenue"] == 10_000.0
    assert suggested["ebitda_margin"] == 0.2
    assert suggested["da_pct"] == 0.04
    assert suggested["tax_rate"] == pytest.approx(200 / 1200)
    assert suggested["capex_pct"] == 0.05
    assert suggested["shares_outstanding"] == 1_000.0
    assert suggested["revenue_growth"] == 0.25


def test_dcf_still_required_never_guesses_wacc():
    fin = _sample_financials()
    suggested = suggest_dcf_inputs(fin)
    still = dcf_still_required(suggested)
    assert "wacc" in still
    assert "terminal_growth" in still
    assert "projection_years" in still
    assert "nwc_pct" in still
