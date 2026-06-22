"""Tests for comps field_status and coverage integration."""

from engine.comps import extract_fiscal_snapshot


def test_gross_margin_not_applicable_for_platform_business():
    fin = {
        "ticker": "V",
        "statements": {
            "income": {
                "annual": [
                    {
                        "fiscal_year": 2025,
                        "fiscal_period": "FY",
                        "line_items": [
                            {"key": "revenue", "label": "Revenue", "value": 40e9, "unit": "USD"},
                            {"key": "operating_income", "label": "OI", "value": 24e9, "unit": "USD"},
                            {"key": "net_income", "label": "NI", "value": 20e9, "unit": "USD"},
                        ],
                    }
                ],
                "quarterly": [],
            },
            "balance": {"annual": [], "quarterly": []},
            "cashflow": {"annual": [], "quarterly": []},
        },
    }
    snap = extract_fiscal_snapshot(fin, 2025)
    assert snap["gross_margin"] is None
    gm_status = snap["field_status"]["gross_margin"]
    assert gm_status["status"] in ("not_applicable", "missing")


def test_field_status_present_for_revenue():
    fin = {
        "ticker": "KO",
        "statements": {
            "income": {
                "annual": [
                    {
                        "fiscal_year": 2024,
                        "fiscal_period": "FY",
                        "line_items": [
                            {"key": "revenue", "label": "Revenue", "value": 1e9, "unit": "USD"},
                        ],
                    }
                ],
                "quarterly": [],
            },
            "balance": {"annual": [], "quarterly": []},
            "cashflow": {"annual": [], "quarterly": []},
        },
    }
    snap = extract_fiscal_snapshot(fin, 2024)
    assert snap["field_status"]["revenue"]["status"] == "present"
