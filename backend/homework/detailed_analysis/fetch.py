"""Fetch 5-year income / balance / cashflow DataFrames for detailed analysis."""

from __future__ import annotations

from homework.hero_analysis_explore import fetch_hero_analysis


def fetch_detailed_statements(*, ticker: str, years: int = 5):
    """Return hero fetch result; caller reads income/balance/cashflow standard DFs."""
    return fetch_hero_analysis(ticker=ticker, years=years)
