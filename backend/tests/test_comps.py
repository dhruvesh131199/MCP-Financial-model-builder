"""Tests for comparative analysis engine."""

import pytest

from engine.comps import (
    build_comparative_report,
    compute_market_ev,
    compute_net_debt,
    compute_tier_b_ratios,
    extract_fiscal_snapshot,
)


def _financials(
    ticker: str,
    fiscal_years: dict[int, dict[str, float]],
) -> dict:
    annual = []
    for fy, items in sorted(fiscal_years.items(), reverse=True):
        annual.append(
            {
                "fiscal_year": fy,
                "fiscal_period": "FY",
                "form": "10-K",
                "line_items": [
                    {"key": k, "label": k, "value": v, "unit": "USD"} for k, v in items.items()
                ],
            }
        )
    return {
        "ticker": ticker,
        "entity_name": ticker,
        "statements": {
            "income": {"annual": annual, "quarterly": []},
            "balance": {"annual": annual, "quarterly": []},
            "cashflow": {"annual": annual, "quarterly": []},
        },
    }


def test_compute_net_debt_total_debt():
    items = {"total_debt": 500.0, "cash": 100.0}
    assert compute_net_debt(items) == 400.0


def test_extract_fiscal_snapshot_and_growth():
    fin = _financials(
        "KO",
        {
            2024: {
                "revenue": 1_000_000_000,
                "net_income": 100_000_000,
                "stockholders_equity": 500_000_000,
                "total_assets": 2_000_000_000,
                "operating_income": 150_000_000,
                "depreciation": 20_000_000,
                "amortization": 5_000_000,
                "ebitda": 175_000_000,
                "cash": 50_000_000,
                "total_debt": 200_000_000,
                "shares_outstanding": 4_000_000_000,
            },
            2023: {"revenue": 900_000_000, "net_income": 90_000_000},
        },
    )
    snap = extract_fiscal_snapshot(fin, 2024)
    assert snap["revenue"] == 1_000_000_000
    assert snap["net_debt"] == 150_000_000
    assert snap["revenue_growth_yoy"] == pytest.approx(1 / 9)
    assert snap["net_margin"] == pytest.approx(0.10)


def test_tier_b_ratios():
    snap = {
        "revenue": 1_000_000_000,
        "net_income": 100_000_000,
        "stockholders_equity": 500_000_000,
        "ebitda": 200_000_000,
        "net_debt": 100_000_000,
        "shares_outstanding": 1_000_000_000,
    }
    market = {"stock_price": 10.0, "market_cap_usd": 10_000_000_000.0, "ok": True}
    ratios = compute_tier_b_ratios(snap, market)
    assert ratios["market_enterprise_value"] == pytest.approx(10_100_000_000.0)
    assert ratios["pe_ratio"] == pytest.approx(100.0)
    assert ratios["pb_ratio"] == pytest.approx(20.0)
    assert ratios["ev_to_sales"] == pytest.approx(10.1)
    assert ratios["ev_to_ebitda"] == pytest.approx(50.5)


def test_build_comparative_report_target_and_median():
    target_fin = _financials(
        "KO",
        {2024: {"revenue": 100.0, "net_income": 10.0, "stockholders_equity": 50.0}},
    )
    peer_fin = _financials(
        "PEP",
        {2024: {"revenue": 80.0, "net_income": 8.0, "stockholders_equity": 40.0}},
    )
    report = build_comparative_report(
        target={
            "ticker": "KO",
            "company_name": "Coca-Cola",
            "is_target": True,
            "financials": target_fin,
            "market_data": {"stock_price": 1.0, "market_cap_usd": 100.0, "ok": True},
        },
        peers=[
            {
                "ticker": "PEP",
                "company_name": "PepsiCo",
                "is_target": False,
                "financials": peer_fin,
                "market_data": {"stock_price": 2.0, "market_cap_usd": 80.0, "ok": True},
            }
        ],
        fiscal_year=2024,
    )
    assert report["companies"][0]["is_target"] is True
    assert report["summary"]["peer_median_pe"] is not None


def test_partial_market_data_failure():
    fin = _financials("X", {2024: {"revenue": 100.0, "net_income": 10.0}})
    report = build_comparative_report(
        target={
            "ticker": "X",
            "is_target": True,
            "financials": fin,
            "market_data": {"ok": False},
        },
        peers=[],
        fiscal_year=2024,
    )
    assert "X" in report["market_data_errors"]
    assert report["companies"][0]["multiples"]["pe_ratio"] is None


def test_compute_market_ev():
    assert compute_market_ev(1000.0, 200.0) == 1200.0
    assert compute_market_ev(1000.0, None) == 1000.0
