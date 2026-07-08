"""Comparative analysis engine — pure Python, no HTTP/MCP."""

from __future__ import annotations

import statistics
from typing import Any

from ingest.coverage import build_comps_field_status, build_coverage_report


def _period_line_items(financials: dict, fiscal_year: int) -> dict[str, float]:
    """Merge income, balance, cashflow line items for one fiscal year."""
    merged: dict[str, float] = {}
    statements = financials.get("statements") or {}
    for stmt in statements.values():
        for period in stmt.get("annual") or []:
            if int(period.get("fiscal_year", 0)) != fiscal_year:
                continue
            for li in period.get("line_items") or []:
                merged[li["key"]] = float(li["value"])
    return merged


def _prior_fiscal_year(financials: dict, fiscal_year: int) -> int | None:
    statements = financials.get("statements") or {}
    income = statements.get("income") or {}
    years = sorted(
        {int(p["fiscal_year"]) for p in income.get("annual") or []},
        reverse=True,
    )
    prior = [y for y in years if y < fiscal_year]
    return prior[0] if prior else None


def _safe_div(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return num / den


def compute_net_debt(items: dict[str, float]) -> float | None:
    cash = items.get("cash")
    total_debt = items.get("total_debt")
    if total_debt is None:
        ltd = items.get("long_term_debt") or 0.0
        std = items.get("short_term_debt") or 0.0
        total_debt = ltd + std if (ltd or std) else None
    if total_debt is None or cash is None:
        return None
    return total_debt - cash


def compute_operating_nwc_from_items(items: dict[str, float]) -> float | None:
    """Operating NWC proxy: (AR + Inventory) - Accounts Payable."""
    receivables = items.get("accounts_receivable")
    inventory = items.get("inventory")
    payables = items.get("accounts_payable")
    if receivables is None or inventory is None or payables is None:
        return None
    return float(receivables) + float(inventory) - float(payables)


def extract_fiscal_snapshot(financials: dict, fiscal_year: int) -> dict[str, Any]:
    items = _period_line_items(financials, fiscal_year)
    prior_year = _prior_fiscal_year(financials, fiscal_year)
    prior_items = (
        _period_line_items(financials, prior_year) if prior_year is not None else {}
    )

    revenue = items.get("revenue")
    net_income = items.get("net_income")
    equity = items.get("stockholders_equity")
    assets = items.get("total_assets")
    shares = items.get("shares_outstanding") or items.get("weighted_avg_shares_diluted")
    ebitda = items.get("ebitda")
    net_debt = compute_net_debt(items)

    rev_growth = None
    if revenue is not None and prior_items.get("revenue"):
        prev = prior_items["revenue"]
        if prev:
            rev_growth = (revenue - prev) / prev

    ni_growth = None
    if net_income is not None and prior_items.get("net_income"):
        prev = prior_items["net_income"]
        if prev:
            ni_growth = (net_income - prev) / prev

    gross_profit = items.get("gross_profit")
    op_income = items.get("operating_income")
    ocf = items.get("operating_cash_flow")
    fcf = items.get("free_cash_flow")

    stored_coverage = financials.get("coverage")
    if stored_coverage and isinstance(stored_coverage, dict):
        coverage = stored_coverage
    else:
        coverage = {
            k: v.model_dump() if hasattr(v, "model_dump") else v
            for k, v in build_coverage_report(financials, fiscal_year).items()
        }

    snapshot = {
        "fiscal_year": fiscal_year,
        "revenue": revenue,
        "net_income": net_income,
        "total_assets": assets,
        "stockholders_equity": equity,
        "gross_margin": _safe_div(gross_profit, revenue),
        "operating_margin": _safe_div(op_income, revenue),
        "net_margin": _safe_div(net_income, revenue),
        "roe": _safe_div(net_income, equity),
        "roa": _safe_div(net_income, assets),
        "net_debt": net_debt,
        "debt_to_equity": _safe_div(
            items.get("total_debt")
            or ((items.get("long_term_debt") or 0) + (items.get("short_term_debt") or 0))
            or None,
            equity,
        ),
        "operating_cash_flow": ocf,
        "capex": items.get("capex"),
        "free_cash_flow": fcf,
        "fcf_margin": _safe_div(fcf, revenue),
        "revenue_growth_yoy": rev_growth,
        "net_income_growth_yoy": ni_growth,
        "book_value_per_share": _safe_div(equity, shares),
        "shares_outstanding": shares,
        "ebitda": ebitda,
        "eps_diluted": items.get("eps_diluted"),
    }

    snapshot["field_status"] = build_comps_field_status(snapshot, coverage)
    snapshot["missing_metrics"] = [
        k for k, st in snapshot["field_status"].items() if st.get("status") == "missing"
    ]

    return snapshot


def compute_market_cap(stock_price: float | None, shares: float | None) -> float | None:
    if stock_price is None or shares is None:
        return None
    return stock_price * shares


def compute_market_ev(market_cap: float | None, net_debt: float | None) -> float | None:
    if market_cap is None:
        return None
    return market_cap + (net_debt or 0.0)


def compute_tier_b_ratios(
    snapshot: dict[str, Any],
    market_data: dict[str, Any],
) -> dict[str, Any]:
    stock_price = market_data.get("stock_price")
    market_cap = market_data.get("market_cap_usd")
    finnhub_shares = market_data.get("shares_outstanding")
    shares = snapshot.get("shares_outstanding") or finnhub_shares

    if market_cap is None:
        market_cap = compute_market_cap(stock_price, shares)

    net_debt = snapshot.get("net_debt")
    market_ev = compute_market_ev(market_cap, net_debt)
    revenue = snapshot.get("revenue")
    net_income = snapshot.get("net_income")
    equity = snapshot.get("stockholders_equity")
    ebitda = snapshot.get("ebitda")

    pe = _safe_div(market_cap, net_income)
    if pe is None and stock_price and snapshot.get("eps_diluted"):
        pe = _safe_div(stock_price, snapshot["eps_diluted"])

    pb = _safe_div(market_cap, equity)
    if pb is None and stock_price and snapshot.get("book_value_per_share"):
        pb = _safe_div(stock_price, snapshot["book_value_per_share"])

    return {
        "stock_price": stock_price,
        "market_cap_usd": market_cap,
        "market_enterprise_value": market_ev,
        "pe_ratio": pe,
        "pb_ratio": pb,
        "ev_to_sales": _safe_div(market_ev, revenue),
        "ev_to_ebitda": _safe_div(market_ev, ebitda),
    }


def _median_of(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def build_comparative_report(
    *,
    target: dict[str, Any],
    peers: list[dict[str, Any]],
    fiscal_year: int,
    fiscal_year_note: str | None = None,
) -> dict[str, Any]:
    companies_in: list[dict[str, Any]] = [target, *peers]
    rows: list[dict[str, Any]] = []
    market_data_errors: list[str] = []

    for company in companies_in:
        financials = company.get("financials") or {}
        snapshot = company.get("snapshot") or extract_fiscal_snapshot(
            financials, fiscal_year
        )
        market_data = company.get("market_data") or {}
        mkt_ok = bool(market_data.get("ok"))
        mkt_errors = market_data.get("errors") or []
        if not mkt_ok:
            market_data_errors.append(company.get("ticker", "?"))

        coverage_raw = financials.get("coverage") or build_coverage_report(
            financials, fiscal_year
        )
        if coverage_raw and isinstance(next(iter(coverage_raw.values()), {}), dict):
            coverage = coverage_raw
        else:
            coverage = {
                k: (v.model_dump() if hasattr(v, "model_dump") else v)
                for k, v in coverage_raw.items()
            }

        snapshot = {
            **snapshot,
            "field_status": build_comps_field_status(
                snapshot,
                coverage,
                market_ok=mkt_ok,
                market_errors=mkt_errors,
            ),
        }

        tier_b = compute_tier_b_ratios(snapshot, market_data) if mkt_ok else {
            "stock_price": None,
            "market_cap_usd": None,
            "market_enterprise_value": None,
            "pe_ratio": None,
            "pb_ratio": None,
            "ev_to_sales": None,
            "ev_to_ebitda": None,
        }

        rows.append(
            {
                "ticker": company.get("ticker"),
                "company_name": company.get("company_name")
                or financials.get("entity_name"),
                "is_target": company.get("is_target", False),
                "fundamentals": snapshot,
                "market_data": {
                    "stock_price": market_data.get("stock_price"),
                    "market_cap_usd": market_data.get("market_cap_usd"),
                    "as_of": market_data.get("as_of"),
                    "source": market_data.get("source"),
                    "exchange": market_data.get("exchange"),
                    "industry": market_data.get("industry"),
                    "errors": mkt_errors,
                    "ok": mkt_ok,
                },
                "multiples": tier_b,
            }
        )

    peer_rows = [r for r in rows if not r["is_target"]]

    def _peer_medians(key_path: str) -> float | None:
        vals: list[float] = []
        for row in peer_rows:
            obj: Any = row
            for part in key_path.split("."):
                obj = (obj or {}).get(part)
            if isinstance(obj, (int, float)) and obj is not None:
                vals.append(float(obj))
        return _median_of(vals)

    summary = {
        "peer_median_pe": _peer_medians("multiples.pe_ratio"),
        "peer_median_pb": _peer_medians("multiples.pb_ratio"),
        "peer_median_ev_to_sales": _peer_medians("multiples.ev_to_sales"),
        "peer_median_ev_to_ebitda": _peer_medians("multiples.ev_to_ebitda"),
        "peer_median_net_margin": _peer_medians("fundamentals.net_margin"),
        "peer_median_revenue_growth_yoy": _peer_medians(
            "fundamentals.revenue_growth_yoy"
        ),
    }

    return {
        "model_type": "comparative",
        "fiscal_year_used": fiscal_year,
        "fiscal_year_note": fiscal_year_note,
        "target": {"ticker": target.get("ticker"), "company_name": target.get("company_name")},
        "peers": [{"ticker": p.get("ticker"), "company_name": p.get("company_name")} for p in peers],
        "companies": rows,
        "summary": summary,
        "market_data_errors": market_data_errors,
    }
