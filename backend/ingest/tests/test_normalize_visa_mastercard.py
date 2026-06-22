"""Tests for Visa/Mastercard-style SEC normalization."""

import pytest

from ingest.normalize import normalize_company_facts

MA_END = "2025-12-31"

MA_PROFIT_LOSS_FIXTURE = {
    "entityName": "Mastercard Inc",
    "facts": {
        "us-gaap": {
            "Revenues": {
                "units": {
                    "USD": [
                        {
                            "val": 32791000000,
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2026-02-11",
                            "end": MA_END,
                        },
                    ]
                }
            },
            "OperatingIncomeLoss": {
                "units": {
                    "USD": [
                        {
                            "val": 18897000000,
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "end": MA_END,
                        },
                    ]
                }
            },
            "ProfitLoss": {
                "units": {
                    "USD": [
                        {
                            "val": 14968000000,
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2026-02-11",
                            "start": "2025-01-01",
                            "end": MA_END,
                        },
                    ]
                }
            },
            "EarningsPerShareDiluted": {
                "units": {
                    "USD/shares": [
                        {"val": 16.52, "fy": 2025, "fp": "FY", "form": "10-K", "end": MA_END},
                    ]
                }
            },
            "WeightedAverageNumberOfDilutedSharesOutstanding": {
                "units": {
                    "shares": [
                        {"val": 906000000, "fy": 2025, "fp": "FY", "form": "10-K", "end": MA_END},
                    ]
                }
            },
            "DepreciationAndAmortization": {
                "units": {
                    "USD": [
                        {"val": 1143000000, "fy": 2025, "fp": "FY", "form": "10-K", "end": MA_END},
                    ]
                }
            },
            "AmortizationOfIntangibleAssets": {
                "units": {
                    "USD": [
                        {"val": 760000000, "fy": 2025, "fp": "FY", "form": "10-K", "end": MA_END},
                    ]
                }
            },
        },
        "dei": {
            "EntityCommonStockSharesOutstanding": {
                "units": {
                    "shares": [
                        {"val": 900000000, "fy": 2025, "fp": "FY", "form": "10-K", "end": MA_END},
                    ]
                }
            }
        },
    },
}

V_END = "2025-09-30"

V_VISA_FIXTURE = {
    "entityName": "VISA INC.",
    "facts": {
        "us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {
                    "USD": [
                        {"val": 40000000000, "fy": 2025, "fp": "FY", "form": "10-K", "end": V_END},
                    ]
                }
            },
            "OperatingIncomeLoss": {
                "units": {
                    "USD": [
                        {"val": 23994000000, "fy": 2025, "fp": "FY", "form": "10-K", "end": V_END},
                    ]
                }
            },
            "NetIncomeLoss": {
                "units": {
                    "USD": [
                        {
                            "val": 20058000000,
                            "fy": 2025,
                            "fp": "FY",
                            "form": "10-K",
                            "start": "2024-10-01",
                            "end": V_END,
                        },
                    ]
                }
            },
            "DepreciationAndAmortization": {
                "units": {
                    "USD": [
                        {"val": 1220000000, "fy": 2025, "fp": "FY", "form": "10-K", "end": V_END},
                    ]
                }
            },
            "AmortizationOfIntangibleAssets": {
                "units": {
                    "USD": [
                        {"val": 79000000, "fy": 2025, "fp": "FY", "form": "10-K", "end": V_END},
                    ]
                }
            },
            "WeightedAverageNumberOfDilutedSharesOutstanding": {
                "units": {
                    "shares": [
                        {"val": 2100000000, "fy": 2025, "fp": "FY", "form": "10-K", "end": V_END},
                    ]
                }
            },
        },
        "dei": {
            "EntityCommonStockSharesOutstanding": {
                "units": {
                    "shares": [
                        {"val": 1900000000, "fy": 2025, "fp": "FY", "form": "10-K", "end": V_END},
                    ]
                }
            }
        },
    },
}


def _fy2025_keys(result, stmt: str) -> dict[str, float]:
    period = result.statements[stmt].annual[0]
    return {li.key: li.value for li in period.line_items}


def test_mastercard_profit_loss_maps_to_net_income():
    result = normalize_company_facts(MA_PROFIT_LOSS_FIXTURE, ticker="MA", cik="1141391")
    income = _fy2025_keys(result, "income")
    assert income["revenue"] == 32791000000
    assert income["net_income"] == 14968000000
    assert income.get("eps_diluted") == 16.52


def test_mastercard_coverage_has_net_income():
    result = normalize_company_facts(MA_PROFIT_LOSS_FIXTURE, ticker="MA", cik="1141391")
    assert result.coverage is not None
    assert result.coverage["net_income"].status == "present"
    assert "ProfitLoss" in (result.coverage["net_income"].reason or "")


def test_visa_derives_eps_from_net_income_and_shares():
    result = normalize_company_facts(V_VISA_FIXTURE, ticker="V", cik="1403161")
    income = _fy2025_keys(result, "income")
    assert income["net_income"] == 20058000000
    assert "eps_diluted" in income
    assert income["eps_diluted"] == pytest.approx(20058000000 / 2100000000)


def test_visa_dei_shares_on_balance():
    result = normalize_company_facts(V_VISA_FIXTURE, ticker="V", cik="1403161")
    balance = _fy2025_keys(result, "balance")
    assert balance.get("shares_outstanding") == 1900000000


def test_gross_profit_not_applicable_in_coverage():
    result = normalize_company_facts(MA_PROFIT_LOSS_FIXTURE, ticker="MA", cik="1141391")
    assert result.coverage is not None
    assert result.coverage["cost_of_revenue"].status == "not_applicable"
