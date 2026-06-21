"""Normalize tests with a minimal SEC companyfacts fixture."""

from ingest.normalize import normalize_company_facts

FIXTURE = {
    "entityName": "Test Corp",
    "facts": {
        "us-gaap": {
            "Revenues": {
                "units": {
                    "USD": [
                        {
                            "val": 1000000000,
                            "fy": 2024,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2025-01-15",
                        },
                        {
                            "val": 200000000,
                            "fy": 2025,
                            "fp": "Q1",
                            "form": "10-Q",
                            "filed": "2025-04-15",
                        },
                        {
                            "val": 900000000,
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2024-01-15",
                        },
                        {
                            "val": 800000000,
                            "fy": 2022,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-01-15",
                        },
                        {
                            "val": 700000000,
                            "fy": 2021,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2022-01-15",
                        },
                        {
                            "val": 600000000,
                            "fy": 2020,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2021-01-15",
                        },
                        {
                            "val": 500000000,
                            "fy": 2019,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2020-01-15",
                        },
                    ]
                }
            },
            "NetIncomeLoss": {
                "units": {
                    "USD": [
                        {"val": 100000000, "fy": 2024, "fp": "FY", "form": "10-K"},
                        {"val": 25000000, "fy": 2025, "fp": "Q1", "form": "10-Q"},
                        {"val": 90000000, "fy": 2023, "fp": "FY", "form": "10-K"},
                    ]
                }
            },
            "NetCashProvidedByUsedInOperatingActivities": {
                "units": {
                    "USD": [
                        {"val": 150000000, "fy": 2024, "fp": "FY", "form": "10-K"},
                    ]
                }
            },
            "PaymentsToAcquirePropertyPlantAndEquipment": {
                "units": {
                    "USD": [
                        {"val": 50000000, "fy": 2024, "fp": "FY", "form": "10-K"},
                    ]
                }
            },
        }
    },
}


def test_normalize_income_annual():
    result = normalize_company_facts(FIXTURE, ticker="TEST", cik="0000000001")
    income = result.statements["income"]
    assert len(income.annual) >= 1
    assert income.annual[0].fiscal_year == 2024
    keys = {li.key for li in income.annual[0].line_items}
    assert "revenue" in keys
    assert "net_income" in keys


def test_normalize_quarterly():
    result = normalize_company_facts(FIXTURE, ticker="TEST", cik="0000000001")
    income = result.statements["income"]
    assert len(income.quarterly) == 1
    assert income.quarterly[0].fiscal_period == "Q1"


def test_free_cash_flow_derived():
    result = normalize_company_facts(FIXTURE, ticker="TEST", cik="0000000001")
    cf = result.statements["cashflow"].annual[0]
    fcf = next(li for li in cf.line_items if li.key == "free_cash_flow")
    assert fcf.value == 100000000.0
