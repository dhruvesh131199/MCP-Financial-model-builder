"""Tests for fiscal year / quarter mapping."""

from ingest.fiscal_calendar import fiscal_quarter_from_period_end, fiscal_year_from_period_end


def test_apple_annual_fy_from_period_end():
    fy_end = "0926"
    assert fiscal_year_from_period_end("2025-09-27", fy_end_mmdd=fy_end) == 2025
    assert fiscal_year_from_period_end("2023-09-30", fy_end_mmdd=fy_end) == 2023


def test_apple_quarterly_fy_labels():
    fy_end = "0926"
    # FY2024 Q1 ends Dec 2023
    assert fiscal_year_from_period_end("2023-12-30", fy_end_mmdd=fy_end) == 2024
    # FY2023 Q3
    assert fiscal_year_from_period_end("2023-07-01", fy_end_mmdd=fy_end) == 2023


def test_amd_calendar_fy():
    fy_end = "1226"
    assert fiscal_year_from_period_end("2023-12-30", fy_end_mmdd=fy_end) == 2023
    assert fiscal_quarter_from_period_end("2023-09-30", fy_end_mmdd=fy_end) in (
        "Q1",
        "Q2",
        "Q3",
        "Q4",
    )
