"""Tests for SEC financial filtering and dedup keys."""

from ingest.tests.test_normalize import FIXTURE
from ingest.normalize import normalize_company_facts
from services.sec_financials import (
    build_dedup_key,
    build_file_name,
    filter_financials,
    included_fiscal_years,
)


def _sample_financials():
    return normalize_company_facts(FIXTURE, ticker="TEST", cik="0000000001")


def test_filter_fiscal_year_2023():
    financials = _sample_financials()
    filtered = filter_financials(financials, fiscal_years=[2023])
    income = filtered.statements["income"]
    assert all(p.fiscal_year == 2023 for p in income.annual)
    assert included_fiscal_years(filtered) == [2023]


def test_filter_max_years_5():
    financials = _sample_financials()
    filtered = filter_financials(financials, max_years=5)
    years = included_fiscal_years(filtered)
    assert len(years) <= 5
    assert 2024 in years


def test_filter_annual_only():
    financials = _sample_financials()
    filtered = filter_financials(financials, include_quarterly=False)
    income = filtered.statements["income"]
    assert len(income.quarterly) == 0
    assert len(income.annual) > 0


def test_build_dedup_key_differs_by_scope():
    key_a = build_dedup_key(
        "AAPL",
        fiscal_years=[2023],
        max_years=5,
        include_annual=True,
        include_quarterly=True,
        statements=["income", "balance", "cashflow"],
    )
    key_b = build_dedup_key(
        "AAPL",
        fiscal_years=None,
        max_years=5,
        include_annual=True,
        include_quarterly=True,
        statements=["income", "balance", "cashflow"],
    )
    assert key_a != key_b


def test_build_file_name():
    assert build_file_name("aapl", fiscal_years=[2023], max_years=5) == "AAPL — FY2023"
    assert build_file_name("tsla", fiscal_years=None, max_years=5) == "TSLA — 5Y Financials"
