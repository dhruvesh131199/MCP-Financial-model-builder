"""Tests for edgartools fetch helpers."""

from ingest.edgar_fetch import _annual_filing_count


def test_annual_filing_count_requests_one_extra_10k():
    assert _annual_filing_count(5) == 6
    assert _annual_filing_count(1) == 2
    assert _annual_filing_count(0) == 1
