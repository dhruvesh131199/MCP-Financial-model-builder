"""Tests for 10-K fetch fiscal year resolution."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from helper.rag.fetch_annual import (
    _filing_fiscal_year,
    _resolve_10k_filing,
    peek_latest_annual_filing_meta,
)


def _mock_filing(por: str, fdate: str, accession: str = "acc"):
    f = MagicMock()
    f.period_of_report = por
    f.filing_date = fdate
    f.accession_no = accession
    f.form = "10-K"
    f.primary_document = "a.htm"
    return f


def test_filing_fiscal_year_from_period():
    assert _filing_fiscal_year(_mock_filing("2024-01-31", "2024-03-15")) == 2024


def test_resolve_10k_filing_by_fiscal_year():
    company = MagicMock()
    f2023 = _mock_filing("2023-01-31", "2023-03-01", "a")
    f2024 = _mock_filing("2024-01-31", "2024-03-01", "b")
    filings = MagicMock()
    filings.latest.return_value = f2024
    filings.__iter__ = lambda self: iter([f2023, f2024])
    company.get_filings.return_value = filings

    picked = _resolve_10k_filing(company, 2023)
    assert picked.accession_no == "a"


def test_resolve_10k_filing_missing_year_raises():
    company = MagicMock()
    filings = MagicMock()
    filings.__iter__ = lambda self: iter([_mock_filing("2024-01-31", "2024-03-01")])
    company.get_filings.return_value = filings
    company.ticker = "WMT"
    with pytest.raises(ValueError, match="2020"):
        _resolve_10k_filing(company, 2020)


@patch("helper.rag.fetch_annual.Company")
def test_peek_with_fiscal_year(mock_company_cls):
    company = MagicMock()
    mock_company_cls.return_value = company
    f = _mock_filing("2024-01-31", "2024-03-15")
    filings = MagicMock()
    filings.__iter__ = lambda self: iter([f])
    company.get_filings.return_value = filings
    company.name = "Walmart Inc."
    company.cik = "104169"

    meta = peek_latest_annual_filing_meta(ticker="WMT", fiscal_year=2024)
    assert meta.ticker == "WMT"
    assert meta.period_of_report == "2024-01-31"
