"""Live edgartools integration — requires network."""

import pytest

from ingest.edgar_fetch import fetch_edgar_frames
from ingest.edgar_adapter import adapt_edgar_to_financials

AMD_10K = {
    2025: {"revenue": 34_639_000_000, "net_income": 4_335_000_000},
    2024: {"revenue": 25_785_000_000, "net_income": 1_641_000_000},
    2023: {"revenue": 22_680_000_000, "net_income": 854_000_000},
}


def _annual_values(result, fiscal_year: int) -> dict[str, float]:
    for period in result.statements["income"].annual:
        if period.fiscal_year == fiscal_year:
            return {li.key: li.value for li in period.line_items}
    raise AssertionError(f"FY{fiscal_year} missing")


@pytest.mark.parametrize("ticker", ["AMD", "NVDA"])
def test_edgartools_live_income_matches_10k(ticker: str):
    pytest.importorskip("dotenv")
    from dotenv import load_dotenv

    load_dotenv()
    expected = AMD_10K if ticker == "AMD" else None
    if expected is None:
        pytest.skip("reference table only for AMD in this test")

    fetch = fetch_edgar_frames(
        ticker=ticker,
        max_years=5,
        include_quarterly=False,
        statements=["income"],
    )
    result = adapt_edgar_to_financials(fetch, fetch_scope=["income"])
    assert result.ingest_source == "edgartools"
    assert len(result.statements["income"].annual) == 5

    for year, targets in expected.items():
        values = _annual_values(result, year)
        assert values["revenue"] == targets["revenue"]
        assert values["net_income"] == targets["net_income"]


def test_sec_financials_uses_edgartools_primary():
    pytest.importorskip("dotenv")
    from dotenv import load_dotenv

    load_dotenv()
    from services.sec_financials import fetch_sec_financials

    result = fetch_sec_financials(ticker="AMD", max_years=5, include_quarterly=False)
    assert result.ingest_source == "edgartools"
    income = result.statements["income"].annual
    assert len(income) == 5
    years = [p.fiscal_year for p in income]
    assert years == sorted(years, reverse=True)
    rev = next(li.value for li in income[0].line_items if li.key == "revenue")
    assert rev == 34_639_000_000


def test_sec_financials_amd_three_years():
    pytest.importorskip("dotenv")
    from dotenv import load_dotenv

    load_dotenv()
    from services.sec_financials import fetch_sec_financials

    result = fetch_sec_financials(ticker="AMD", max_years=3, include_quarterly=False)
    assert result.ingest_source == "edgartools"
    income = result.statements["income"].annual[0]
    rev = next(li.value for li in income.line_items if li.key == "revenue")
    assert rev == 34_639_000_000
