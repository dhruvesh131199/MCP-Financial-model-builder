"""Live edgartools integration — requires network."""

import pytest

from ingest.edgar_fetch import fetch_edgar_statements

AMD_10K = {
    2025: {"revenue": 34_639_000_000, "net_income": 4_335_000_000},
    2024: {"revenue": 25_785_000_000, "net_income": 1_641_000_000},
    2023: {"revenue": 22_680_000_000, "net_income": 854_000_000},
}

AAPL_FY2023 = {"revenue": 383_285_000_000, "net_income": 96_995_000_000}
JPM_LATEST_REVENUE_MIN = 150_000_000_000


def _annual_values(result, fiscal_year: int) -> dict[str, float]:
    for period in result.statements["income"].annual:
        if period.fiscal_year == fiscal_year:
            return {li.key: li.value for li in period.line_items}
    raise AssertionError(f"FY{fiscal_year} missing")


def _load_env():
    pytest.importorskip("dotenv")
    from dotenv import load_dotenv

    load_dotenv()


@pytest.mark.parametrize("ticker", ["AMD", "NVDA"])
def test_edgartools_live_income_matches_10k(ticker: str):
    _load_env()
    expected = AMD_10K if ticker == "AMD" else None
    if expected is None:
        pytest.skip("reference table only for AMD in this test")

    result = fetch_edgar_statements(
        ticker=ticker,
        cik="0000002488" if ticker == "AMD" else "0001045810",
        entity_name=ticker,
        max_years=5,
        include_quarterly=False,
        statements=["income"],
    )
    assert result.ingest_source == "edgartools"
    assert len(result.statements["income"].annual) == 5

    for year, targets in expected.items():
        values = _annual_values(result, year)
        assert values["revenue"] == targets["revenue"]
        assert values["net_income"] == targets["net_income"]


def test_fetch_latest_year_default_scope():
    _load_env()
    from services.sec_financials import fetch_sec_financials, included_fiscal_years

    result = fetch_sec_financials(
        ticker="AAPL",
        max_years=1,
        include_quarterly=False,
        statements=["income"],
    )
    years = included_fiscal_years(result)
    assert len(years) == 1
    assert len(result.statements["income"].annual) == 1
    assert result.statements["income"].annual[0].fiscal_period == "FY"


def test_fetch_specific_fiscal_year_2023_only():
    _load_env()
    from services.sec_financials import fetch_sec_financials, included_fiscal_years

    result = fetch_sec_financials(
        ticker="AAPL",
        fiscal_years=[2023],
        include_quarterly=False,
        statements=["income"],
    )
    assert included_fiscal_years(result) == [2023]
    values = _annual_values(result, 2023)
    assert values["revenue"] == AAPL_FY2023["revenue"]
    assert values["net_income"] == AAPL_FY2023["net_income"]


def test_fetch_last_five_years():
    _load_env()
    from services.sec_financials import fetch_sec_financials, included_fiscal_years

    result = fetch_sec_financials(
        ticker="AMD",
        max_years=5,
        include_quarterly=False,
        statements=["income"],
    )
    years = included_fiscal_years(result)
    assert len(years) == 5
    assert years == sorted(years, reverse=True)


def test_fetch_quarterly_trailing_four():
    _load_env()
    from services.sec_financials import fetch_sec_financials

    result = fetch_sec_financials(
        ticker="AAPL",
        max_years=1,
        include_annual=False,
        include_quarterly=True,
        statements=["income"],
    )
    quarters = result.statements["income"].quarterly
    assert len(quarters) == 4
    assert all(p.fiscal_period in ("Q1", "Q2", "Q3", "Q4") for p in quarters)


def test_fetch_fiscal_year_2023_quarterly():
    _load_env()
    from services.sec_financials import fetch_sec_financials

    result = fetch_sec_financials(
        ticker="AMD",
        fiscal_years=[2023],
        include_annual=False,
        include_quarterly=True,
        statements=["income"],
    )
    quarters = result.statements["income"].quarterly
    assert len(quarters) >= 3
    assert all(p.fiscal_year == 2023 for p in quarters)


def test_sec_financials_uses_edgartools_primary():
    _load_env()
    from services.sec_financials import fetch_sec_financials

    result = fetch_sec_financials(ticker="AMD", max_years=5, include_quarterly=False)
    assert result.ingest_source == "edgartools"
    income = result.statements["income"].annual
    assert len(income) == 5
    years = [p.fiscal_year for p in income]
    assert years == sorted(years, reverse=True)
    rev = next(li.value for li in income[0].line_items if li.key == "revenue")
    assert rev == 34_639_000_000


def test_jpm_latest_revenue_is_total_not_sub_line():
    _load_env()
    from services.sec_financials import fetch_sec_financials

    result = fetch_sec_financials(ticker="JPM", max_years=1, statements=["income"])
    rev = next(
        li.value
        for li in result.statements["income"].annual[0].line_items
        if li.key == "revenue"
    )
    assert rev > JPM_LATEST_REVENUE_MIN


def test_sec_financials_amd_three_years():
    _load_env()
    from services.sec_financials import fetch_sec_financials

    result = fetch_sec_financials(ticker="AMD", max_years=3, include_quarterly=False)
    assert result.ingest_source == "edgartools"
    income = result.statements["income"].annual[0]
    rev = next(li.value for li in income.line_items if li.key == "revenue")
    assert rev == 34_639_000_000
