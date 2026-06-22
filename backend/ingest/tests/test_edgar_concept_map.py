"""Tests for edgartools standard_concept mapping."""

from ingest.edgar_concept_map import (
    STANDARD_CONCEPT_TO_KEY,
    canonical_key_from_raw,
    canonical_key_from_standard,
    canonical_keys_for_statement,
)


def test_standard_concept_revenue():
    assert canonical_key_from_standard("Revenue") == "revenue"


def test_cashflow_depreciation_expense_maps_to_combined_da():
    assert (
        canonical_key_from_standard("DepreciationExpense", statement="cashflow")
        == "depreciation_and_amortization"
    )
    assert (
        canonical_key_from_standard("DepreciationExpense", statement="income")
        == "depreciation"
    )


def test_raw_tag_eps():
    assert canonical_key_from_raw("us-gaap_EarningsPerShareDiluted") == "eps_diluted"


def test_income_keys_cover_core_metrics():
    keys = set(canonical_keys_for_statement("income"))
    assert "revenue" in keys
    assert "net_income" in keys
    assert "operating_income" in keys


def test_all_standard_mappings_have_canonical_key():
    for concept, key in STANDARD_CONCEPT_TO_KEY.items():
        assert key in canonical_keys_for_statement("income") + canonical_keys_for_statement(
            "balance"
        ) + canonical_keys_for_statement("cashflow")
