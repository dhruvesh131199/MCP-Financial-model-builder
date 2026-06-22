"""Derive partial DCF inputs from normalized SEC financials (millions USD, decimals)."""

from __future__ import annotations

from engine.comps import compute_net_debt, extract_fiscal_snapshot
from ingest.normalize import FinancialStatements


def _normalize_rate(value: float) -> float:
    if abs(value) > 1:
        return value / 100
    return value


def suggest_dcf_inputs(financials: FinancialStatements) -> dict[str, float | str | list[float]]:
    """Return only DCF fields computable from filed/derived SEC data."""
    dump = financials.model_dump()
    income = financials.statements.get("income")
    if not income or not income.annual:
        return {}

    latest_fy = income.annual[0].fiscal_year
    snap = extract_fiscal_snapshot(dump, latest_fy)
    suggested: dict[str, float | str | list[float]] = {}

    if financials.entity_name:
        suggested["company_name"] = financials.entity_name

    revenue = snap.get("revenue")
    if revenue and revenue > 0:
        suggested["base_revenue"] = revenue / 1_000_000

    growth = snap.get("revenue_growth_yoy")
    if growth is not None:
        suggested["revenue_growth"] = _normalize_rate(float(growth))

    if revenue and revenue > 0:
        ebitda = snap.get("ebitda")
        if ebitda is not None:
            suggested["ebitda_margin"] = float(ebitda) / float(revenue)

        ibt = _line_value(dump, latest_fy, "income_before_tax")
        tax = _line_value(dump, latest_fy, "income_tax_expense")
        if ibt and ibt > 0 and tax is not None:
            suggested["tax_rate"] = abs(float(tax)) / float(ibt)

        capex = snap.get("capex")
        if capex is not None:
            suggested["capex_pct"] = abs(float(capex)) / float(revenue)

    net_debt = snap.get("net_debt")
    if net_debt is not None:
        suggested["net_debt"] = float(net_debt) / 1_000_000

    shares = snap.get("shares_outstanding")
    if shares and shares > 0:
        suggested["shares_outstanding"] = float(shares) / 1_000_000

    return suggested


def dcf_still_required(prefilled: dict) -> list[str]:
    from store import REQUIRED_DCF_FIELDS

    missing = [f for f in REQUIRED_DCF_FIELDS if f not in prefilled]
    return missing


def _line_value(financials: dict, fiscal_year: int, key: str) -> float | None:
    for slice_ in (financials.get("statements") or {}).values():
        for period in slice_.get("annual") or []:
            if int(period.get("fiscal_year", 0)) != fiscal_year:
                continue
            for li in period.get("line_items") or []:
                if li.get("key") == key:
                    return float(li["value"])
    return None
