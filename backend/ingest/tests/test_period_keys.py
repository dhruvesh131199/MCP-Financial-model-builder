"""Unit tests for SEC period key logic."""

from ingest.period_keys import period_identity_from_row, pick_best_fact_row


def test_period_identity_uses_end_date_not_fy():
    row = {
        "val": 22680000000,
        "fy": 2025,
        "fp": "FY",
        "form": "10-K",
        "end": "2023-12-30",
    }
    identity = period_identity_from_row(row)
    assert identity is not None
    assert identity.fiscal_year == 2023
    assert identity.fiscal_period == "FY"
    assert identity.sort_key == "2023-12-30"


def test_pick_best_fact_prefers_latest_filed_not_largest_value():
    rows = [
        {"val": 100, "form": "10-K", "filed": "2024-01-01", "end": "2023-12-31", "fp": "FY"},
        {"val": 999, "form": "10-K", "filed": "2025-02-01", "end": "2023-12-31", "fp": "FY"},
    ]
    best = pick_best_fact_row(rows, fiscal_period="FY")
    assert best["val"] == 999
    assert best["filed"] == "2025-02-01"


def test_pick_best_fact_prefers_10k_for_annual():
    rows = [
        {"val": 50, "form": "10-Q", "filed": "2025-04-01", "end": "2024-12-31", "fp": "FY"},
        {"val": 40, "form": "10-K", "filed": "2025-02-01", "end": "2024-12-31", "fp": "FY"},
    ]
    best = pick_best_fact_row(rows, fiscal_period="FY")
    assert best["form"] == "10-K"


def test_frame_fallback_cy2023():
    row = {"val": 1, "fp": "FY", "form": "10-K", "frame": "CY2023"}
    identity = period_identity_from_row(row)
    assert identity is not None
    assert identity.fiscal_year == 2023
    assert identity.fiscal_period == "FY"
