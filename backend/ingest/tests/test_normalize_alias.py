"""Tests for alias fallback and derived line items."""

from ingest.normalize import normalize_company_facts

# AMD-style: Revenues tag present but empty for FY; revenue in alternate tag
AMD_REVENUE_FIXTURE = {
    "entityName": "ADVANCED MICRO DEVICES INC",
    "facts": {
        "us-gaap": {
            "Revenues": {"units": {"USD": []}},
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {
                    "USD": [
                        {
                            "val": 25785000000,
                            "fy": 2024,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2025-02-05",
                            "end": "2024-12-28",
                        },
                        {
                            "val": 34639000000,
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2026-02-04",
                            "end": "2025-12-27",
                        },
                        {
                            "val": 22680000000,
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2026-02-04",
                            "end": "2023-12-30",
                        },
                    ]
                }
            },
            "CostOfRevenue": {
                "units": {
                    "USD": [
                        {
                            "val": 17487000000,
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "end": "2025-12-27",
                        },
                    ]
                }
            },
            "GrossProfit": {
                "units": {
                    "USD": [
                        {
                            "val": 17152000000,
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "end": "2025-12-27",
                        },
                    ]
                }
            },
        }
    },
}


DERIVED_REVENUE_FIXTURE = {
    "entityName": "Derived Only Corp",
    "facts": {
        "us-gaap": {
            "Revenues": {"units": {"USD": []}},
            "CostOfRevenue": {
                "units": {
                    "USD": [{"val": 600, "fy": 2024, "fp": "FY", "form": "10-K"}],
                }
            },
            "GrossProfit": {
                "units": {
                    "USD": [{"val": 400, "fy": 2024, "fp": "FY", "form": "10-K"}],
                }
            },
        }
    },
}


def test_alias_fallback_when_first_tag_empty():
    fin = normalize_company_facts(AMD_REVENUE_FIXTURE, ticker="AMD", cik="2488")
    fy2025 = next(p for p in fin.statements["income"].annual if p.fiscal_year == 2025)
    revenue = next(li for li in fy2025.line_items if li.key == "revenue")
    assert revenue.value == 34639000000.0
    assert revenue.source == "xbrl"
    assert revenue.xbrl_tag == "RevenueFromContractWithCustomerExcludingAssessedTax"


def test_derived_revenue_when_no_xbrl_revenue():
    fin = normalize_company_facts(DERIVED_REVENUE_FIXTURE, ticker="DER", cik="2")
    income = fin.statements["income"].annual[0]
    revenue = next(li for li in income.line_items if li.key == "revenue")
    assert revenue.value == 1000.0
    assert revenue.source == "derived"
    assert revenue.derived_from == ["gross_profit", "cost_of_revenue"]


def test_derived_ebitda_requires_complete_da():
    fixture = {
        "entityName": "EBITDA Corp",
        "facts": {
            "us-gaap": {
                "OperatingIncomeLoss": {
                    "units": {"USD": [{"val": 100, "fy": 2024, "fp": "FY", "form": "10-K"}]}
                },
                "Depreciation": {
                    "units": {"USD": [{"val": 20, "fy": 2024, "fp": "FY", "form": "10-K"}]}
                },
            }
        },
    }
    fin = normalize_company_facts(fixture, ticker="EBIT", cik="1")
    keys = [li.key for li in fin.statements["income"].annual[0].line_items]
    assert "ebitda" not in keys
