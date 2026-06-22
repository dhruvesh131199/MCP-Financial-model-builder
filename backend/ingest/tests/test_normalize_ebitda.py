"""Tests for EBITDA and debt normalization."""

from ingest.normalize import normalize_company_facts

EBITDA_FIXTURE = {
    "entityName": "EBITDA Corp",
    "facts": {
        "us-gaap": {
            "OperatingIncomeLoss": {
                "units": {
                    "USD": [
                        {"val": 100000000, "fy": 2024, "fp": "FY", "form": "10-K"},
                    ]
                }
            },
            "Depreciation": {
                "units": {
                    "USD": [
                        {"val": 20000000, "fy": 2024, "fp": "FY", "form": "10-K"},
                    ]
                }
            },
            "AmortizationOfIntangibleAssets": {
                "units": {
                    "USD": [
                        {"val": 5000000, "fy": 2024, "fp": "FY", "form": "10-K"},
                    ]
                }
            },
            "Assets": {
                "units": {
                    "USD": [
                        {"val": 500000000, "fy": 2024, "fp": "FY", "form": "10-K"},
                    ]
                }
            },
            "CashAndCashEquivalentsAtCarryingValue": {
                "units": {
                    "USD": [
                        {"val": 50000000, "fy": 2024, "fp": "FY", "form": "10-K"},
                    ]
                }
            },
            "Debt": {
                "units": {
                    "USD": [
                        {"val": 150000000, "fy": 2024, "fp": "FY", "form": "10-K"},
                    ]
                }
            },
        }
    },
}


def _annual_keys(financials, key: str) -> list[str]:
    income = financials.statements["income"].annual[0]
    return [li.key for li in income.line_items]


def test_ebitda_derived_from_d_and_a():
    fin = normalize_company_facts(EBITDA_FIXTURE, ticker="EBIT", cik="1")
    income = fin.statements["income"].annual[0]
    ebitda = next(li for li in income.line_items if li.key == "ebitda")
    assert ebitda.value == 125_000_000


def test_total_debt_on_balance_sheet():
    fin = normalize_company_facts(EBITDA_FIXTURE, ticker="EBIT", cik="1")
    balance = fin.statements["balance"].annual[0]
    debt = next(li for li in balance.line_items if li.key == "total_debt")
    assert debt.value == 150_000_000


def test_missing_d_and_a_no_ebitda():
    fixture = {
        "entityName": "No DA",
        "facts": {
            "us-gaap": {
                "OperatingIncomeLoss": {
                    "units": {
                        "USD": [{"val": 100, "fy": 2024, "fp": "FY", "form": "10-K"}]
                    }
                }
            }
        },
    }
    fin = normalize_company_facts(fixture, ticker="NDA", cik="2")
    keys = [li.key for li in fin.statements["income"].annual[0].line_items]
    assert "ebitda" not in keys


def test_ebitda_from_combined_da_tag():
    fixture = {
        "entityName": "Combined DA",
        "facts": {
            "us-gaap": {
                "OperatingIncomeLoss": {
                    "units": {
                        "USD": [{"val": 100, "fy": 2024, "fp": "FY", "form": "10-K"}]
                    }
                },
                "DepreciationAndAmortization": {
                    "units": {
                        "USD": [{"val": 25, "fy": 2024, "fp": "FY", "form": "10-K"}]
                    }
                },
            }
        },
    }
    fin = normalize_company_facts(fixture, ticker="CDA", cik="3")
    income = fin.statements["income"].annual[0]
    ebitda = next(li for li in income.line_items if li.key == "ebitda")
    assert ebitda.value == 125
    assert ebitda.derived_from == ["operating_income", "depreciation_and_amortization"]


def test_ebitda_from_cashflow_da_when_income_incomplete():
    """Income has partial D&A only; cash-flow combined D&A enables EBITDA."""
    fixture = {
        "entityName": "CF DA",
        "facts": {
            "us-gaap": {
                "OperatingIncomeLoss": {
                    "units": {
                        "USD": [{"val": 1000, "fy": 2024, "fp": "FY", "form": "10-K", "end": "2024-12-31"}]
                    }
                },
                "Depreciation": {
                    "units": {
                        "USD": [{"val": 100, "fy": 2024, "fp": "FY", "form": "10-K", "end": "2024-12-31"}]
                    }
                },
                "DepreciationDepletionAndAmortization": {
                    "units": {
                        "USD": [{"val": 250, "fy": 2024, "fp": "FY", "form": "10-K", "end": "2024-12-31"}]
                    }
                },
            }
        },
    }
    fin = normalize_company_facts(fixture, ticker="CFDA", cik="4")
    income = fin.statements["income"].annual[0]
    ebitda = next(li for li in income.line_items if li.key == "ebitda")
    assert ebitda.value == 1250
    assert ebitda.derived_from == ["operating_income", "depreciation_and_amortization"]
