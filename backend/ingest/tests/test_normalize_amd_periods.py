"""AMD-style comparative 10-K columns — period bucketing regression tests."""

import pytest

from ingest.normalize import normalize_company_facts

# Mirrors SEC companyfacts: multiple FY rows share filing `fy` but differ by `end`.
AMD_COMPARATIVE_FIXTURE = {
    "entityName": "ADVANCED MICRO DEVICES INC",
    "facts": {
        "us-gaap": {
            "Revenues": {"units": {"USD": []}},
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {
                    "USD": [
                        {
                            "val": 23601000000,
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2024-01-31",
                            "start": "2021-12-26",
                            "end": "2022-12-31",
                        },
                        {
                            "val": 22680000000,
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2024-01-31",
                            "start": "2023-01-01",
                            "end": "2023-12-30",
                        },
                        {
                            "val": 25785000000,
                            "fy": 2024,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2025-02-05",
                            "start": "2023-12-31",
                            "end": "2024-12-28",
                        },
                        {
                            "val": 22680000000,
                            "fy": 2024,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2025-02-05",
                            "start": "2023-01-01",
                            "end": "2023-12-30",
                        },
                        {
                            "val": 34639000000,
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2026-02-04",
                            "start": "2024-12-29",
                            "end": "2025-12-27",
                        },
                        {
                            "val": 25785000000,
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2026-02-04",
                            "start": "2023-12-31",
                            "end": "2024-12-28",
                        },
                        {
                            "val": 22680000000,
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2026-02-04",
                            "start": "2023-01-01",
                            "end": "2023-12-30",
                        },
                    ]
                }
            },
            "NetIncomeLoss": {
                "units": {
                    "USD": [
                        {
                            "val": 1320000000,
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2024-01-31",
                            "start": "2021-12-26",
                            "end": "2022-12-31",
                        },
                        {
                            "val": 854000000,
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2024-01-31",
                            "start": "2023-01-01",
                            "end": "2023-12-30",
                        },
                        {
                            "val": 1641000000,
                            "fy": 2024,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2025-02-05",
                            "start": "2023-12-31",
                            "end": "2024-12-28",
                        },
                        {
                            "val": 4335000000,
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2026-02-04",
                            "start": "2024-12-29",
                            "end": "2025-12-27",
                        },
                    ]
                }
            },
            "OperatingIncomeLoss": {
                "units": {
                    "USD": [
                        {
                            "val": 3694000000,
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2026-02-04",
                            "start": "2024-12-29",
                            "end": "2025-12-27",
                        },
                        {
                            "val": 1900000000,
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2026-02-04",
                            "start": "2023-12-31",
                            "end": "2024-12-28",
                        },
                    ]
                }
            },
        }
    },
}

# 10-K annual figures (millions) — AMD investor relations / SEC filings
AMD_10K_ANNUAL = {
    2025: {"revenue": 34_639_000_000, "net_income": 4_335_000_000, "operating_income": 3_694_000_000},
    2024: {"revenue": 25_785_000_000, "net_income": 1_641_000_000, "operating_income": 1_900_000_000},
    2023: {"revenue": 22_680_000_000, "net_income": 854_000_000},
    2022: {"revenue": 23_601_000_000, "net_income": 1_320_000_000},
}


def _annual_by_year(result, fiscal_year: int) -> dict[str, float]:
    for period in result.statements["income"].annual:
        if period.fiscal_year == fiscal_year and period.fiscal_period == "FY":
            return {li.key: li.value for li in period.line_items}
    raise AssertionError(f"FY{fiscal_year} not found")


def test_amd_comparative_columns_map_to_correct_fiscal_years():
    result = normalize_company_facts(AMD_COMPARATIVE_FIXTURE, ticker="AMD", cik="2488")
    for year, expected in AMD_10K_ANNUAL.items():
        income = _annual_by_year(result, year)
        assert income["revenue"] == expected["revenue"], f"FY{year} revenue"
        assert income["net_income"] == expected["net_income"], f"FY{year} net income"
        if "operating_income" in expected:
            assert income["operating_income"] == expected["operating_income"], f"FY{year} OI"


def test_amd_fy2023_not_largest_comparative_column():
    """Regression: old code picked $23.6B (FY2022) for FY2023 label."""
    result = normalize_company_facts(AMD_COMPARATIVE_FIXTURE, ticker="AMD", cik="2488")
    income = _annual_by_year(result, 2023)
    assert income["revenue"] == 22_680_000_000
    assert income["net_income"] == 854_000_000


def test_amd_live_sec_matches_10k():
    """Live SEC fetch — validates end-to-end against known 10-K figures."""
    pytest.importorskip("dotenv")
    from dotenv import load_dotenv

    load_dotenv()
    from services.sec_client import fetch_company_facts

    raw = fetch_company_facts("0000002488")
    result = normalize_company_facts(raw, ticker="AMD", cik="2488")

    for year, expected in AMD_10K_ANNUAL.items():
        income = _annual_by_year(result, year)
        assert income["revenue"] == expected["revenue"], f"live FY{year} revenue"
        assert income["net_income"] == expected["net_income"], f"live FY{year} net income"
