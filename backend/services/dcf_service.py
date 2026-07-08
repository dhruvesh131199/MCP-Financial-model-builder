"""DCF draft lifecycle — create template, update inputs, compute valuation."""

from __future__ import annotations

from typing import Any

from engine.dcf import DcfInputs, compute_dcf
from engine.dcf_reference import (
    DcfReferenceHints,
    MAX_REFERENCE_YEARS,
    build_dcf_reference_history,
    ensure_financial_derivations,
)
from services.market_data import fetch_market_snapshot
from services.sec_client import resolve_ticker
from services.sec_financials import fetch_and_cache_statements
from store import (
    get_model_entry,
    save_dcf_draft_model,
    update_model_entry,
    upsert_dcf_computed_from_draft,
)

DCF_REFERENCE_FETCH_YEARS = MAX_REFERENCE_YEARS

MANDATORY_DCF_DRAFT_FIELDS = [
    "base_revenue",
    "wacc",
    "terminal_growth",
]

MANDATORY_DCF_DRAFT_ARRAYS = [
    "revenue_growth",
    "ebitda_margin",
    "da_pct",
    "tax_rate",
    "capex_pct",
    "nwc_pct",
]


def _empty_array(n: int) -> list[None]:
    return [None] * n


def _empty_draft_inputs(projection_years: int) -> dict[str, Any]:
    return {
        "base_revenue": None,
        "wacc": None,
        "terminal_growth": None,
        "revenue_growth": _empty_array(projection_years),
        "ebitda_margin": _empty_array(projection_years),
        "da_pct": _empty_array(projection_years),
        "tax_rate": _empty_array(projection_years),
        "capex_pct": _empty_array(projection_years),
        "nwc_pct": _empty_array(projection_years),
        "net_debt": None,
        "shares_outstanding": None,
    }


def _empty_defaults() -> dict[str, Any]:
    return {
        "revenue_growth": None,
        "tax_rate": None,
        "ebitda_margin": None,
        "da_pct": None,
        "capex_pct": None,
        "nwc_pct": None,
    }


def _shares_hint_m(financials_dump: dict, ticker: str) -> DcfReferenceHints:
    """Latest shares from SEC filing, else Finnhub profile (optional)."""
    from engine.comps import extract_fiscal_snapshot

    income = (financials_dump.get("statements") or {}).get("income") or {}
    annual = income.get("annual") or []
    if not annual:
        return DcfReferenceHints()
    latest_fy = max(int(p["fiscal_year"]) for p in annual)
    snap = extract_fiscal_snapshot(financials_dump, latest_fy)
    sec_shares = snap.get("shares_outstanding")
    market = fetch_market_snapshot(ticker, sec_shares_outstanding=sec_shares)
    if sec_shares and sec_shares > 0:
        return DcfReferenceHints(
            shares_outstanding_m=float(sec_shares) / 1_000_000,
            shares_source="sec",
        )
    finnhub_shares = market.get("shares_outstanding")
    if finnhub_shares and finnhub_shares > 0:
        return DcfReferenceHints(
            shares_outstanding_m=float(finnhub_shares) / 1_000_000,
            shares_source="finnhub",
        )
    return DcfReferenceHints()


def validate_projection_years(projection_years: int | None) -> int:
    if projection_years is None:
        raise ValueError("projection_years is required")
    n = int(projection_years)
    if n < 1 or n > 10:
        raise ValueError("projection_years must be between 1 and 10")
    return n


def _empty_reference_history() -> dict[str, Any]:
    return {
        "ticker": "",
        "company_name": None,
        "fiscal_years": [],
        "rows": [],
        "latest_revenue_usd": None,
        "hints": {},
        "units_note": "All amounts in $M USD.",
    }


def create_dcf_draft(
    session_id: str,
    *,
    ticker: str | None = None,
    company_name: str | None = None,
    projection_years: int,
    model_name: str | None = None,
    base_revenue: float | None = None,
) -> dict:
    """Create an N-year forecast draft; optionally fetch 5Y SEC reference when ticker given."""
    n = validate_projection_years(projection_years)

    sym = (ticker or "").strip().upper() or None
    entity_name = company_name
    reference_dump = _empty_reference_history()

    if sym or (company_name and company_name.strip()):
        resolved = resolve_ticker(company_name=company_name, ticker=sym)
        if "error" in resolved:
            return resolved

        sym = resolved["ticker"]
        entity_name = resolved.get("entity_name") or company_name

        financials, _, _, _, _ = fetch_and_cache_statements(
            session_id,
            company_name=entity_name,
            ticker=sym,
            fiscal_years=None,
            max_years=DCF_REFERENCE_FETCH_YEARS,
            include_annual=True,
            include_quarterly=False,
            statements=["income", "balance", "cashflow"],
        )

        ensure_financial_derivations(financials)
        dump = financials.model_dump()
        shares_hints = _shares_hint_m(dump, sym)
        reference = build_dcf_reference_history(
            financials,
            max_years=DCF_REFERENCE_FETCH_YEARS,
            hints=shares_hints,
        )
        reference_dump = reference.model_dump()

    inputs = _empty_draft_inputs(n)
    hints = reference_dump.get("hints") or {}
    if hints.get("base_revenue_m") is not None:
        inputs["base_revenue"] = hints["base_revenue_m"]
    if hints.get("shares_outstanding_m") is not None:
        inputs["shares_outstanding"] = hints["shares_outstanding_m"]
    if base_revenue is not None:
        inputs["base_revenue"] = float(base_revenue)

    payload = {
        "type": "dcf_draft",
        "ticker": sym or "",
        "company_name": entity_name or model_name,
        "projection_years": n,
        "reference_history": reference_dump,
        "inputs": inputs,
        "defaults": _empty_defaults(),
    }
    entry = save_dcf_draft_model(session_id, payload, name=model_name)
    return {
        "success": True,
        "model_id": entry["id"],
        "model_name": entry["name"],
        "ticker": sym or None,
        "projection_years": n,
        "reference_years": len(reference_dump.get("fiscal_years") or []),
        "prefilled": {
            "base_revenue": inputs.get("base_revenue"),
            "shares_outstanding": inputs.get("shares_outstanding"),
        },
    }


def _get_draft_entry(session_id: str, model_id: str) -> dict:
    entry = get_model_entry(session_id, model_id)
    if not entry:
        raise KeyError("Model not found")
    if entry.get("type") != "dcf_draft":
        raise ValueError("Model is not a DCF draft")
    return entry


def _merge_array(
    existing: list[Any],
    update: list[Any] | None,
    length: int,
) -> list[Any]:
    base = list(existing) if existing else _empty_array(length)
    if len(base) != length:
        base = _empty_array(length)
    if update is None:
        return base
    if len(update) != length:
        raise ValueError(f"Array length must be {length}")
    merged = list(base)
    for i, val in enumerate(update):
        if val is not None:
            merged[i] = val
    return merged


def update_dcf_draft(
    session_id: str,
    model_id: str,
    partial: dict[str, Any],
) -> dict:
    entry = _get_draft_entry(session_id, model_id)
    data = dict(entry.get("data") or {})
    n = int(data.get("projection_years") or 0)
    if n < 1:
        raise ValueError("Invalid draft projection_years")

    inputs = dict(data.get("inputs") or _empty_draft_inputs(n))
    defaults = dict(data.get("defaults") or _empty_defaults())

    scalar_keys = ["base_revenue", "wacc", "terminal_growth", "net_debt", "shares_outstanding"]
    for key in scalar_keys:
        if key in partial and partial[key] is not None:
            inputs[key] = partial[key]

    for key in MANDATORY_DCF_DRAFT_ARRAYS:
        if key in partial:
            inputs[key] = _merge_array(inputs.get(key), partial[key], n)

    default_keys = ["revenue_growth", "tax_rate", "ebitda_margin", "da_pct", "capex_pct", "nwc_pct"]
    for key in default_keys:
        if key in partial.get("defaults", {}) and partial["defaults"][key] is not None:
            defaults[key] = partial["defaults"][key]
        elif key in partial and partial[key] is not None and key in default_keys:
            defaults[key] = partial[key]

    data["inputs"] = inputs
    data["defaults"] = defaults
    updated = update_model_entry(session_id, model_id, data=data)
    summary = summarize_dcf_draft(updated["data"])
    return {"model_id": model_id, **summary}


def summarize_dcf_draft(data: dict) -> dict:
    n = int(data.get("projection_years") or 0)
    inputs = data.get("inputs") or {}
    missing: list[str] = []

    for field in MANDATORY_DCF_DRAFT_FIELDS:
        if inputs.get(field) is None:
            missing.append(field)

    for field in MANDATORY_DCF_DRAFT_ARRAYS:
        arr = inputs.get(field) or []
        if len(arr) != n:
            missing.append(field)
            continue
        for i, val in enumerate(arr):
            if val is None:
                missing.append(f"{field}[{i}]")

    return {
        "projection_years": n,
        "ticker": data.get("ticker"),
        "missing_required": missing,
        "ready": len(missing) == 0,
        "inputs": inputs,
        "defaults": data.get("defaults"),
        "reference_history": data.get("reference_history"),
    }


def _build_dcf_inputs_from_draft(data: dict) -> DcfInputs:
    summary = summarize_dcf_draft(data)
    if not summary["ready"]:
        missing = ", ".join(summary["missing_required"])
        raise ValueError(f"Missing required inputs: {missing}")

    inputs = summary["inputs"]
    n = summary["projection_years"]
    return DcfInputs(
        base_revenue=float(inputs["base_revenue"]),
        revenue_growth=[float(x) for x in inputs["revenue_growth"]],
        ebitda_margin=[float(x) for x in inputs["ebitda_margin"]],
        da_pct=[float(x) for x in inputs["da_pct"]],
        tax_rate=[float(x) for x in inputs["tax_rate"]],
        capex_pct=[float(x) for x in inputs["capex_pct"]],
        nwc_pct=[float(x) for x in inputs["nwc_pct"]],
        wacc=float(inputs["wacc"]),
        terminal_growth=float(inputs["terminal_growth"]),
        projection_years=n,
        net_debt=float(inputs["net_debt"]) if inputs.get("net_debt") is not None else None,
        shares_outstanding=(
            float(inputs["shares_outstanding"])
            if inputs.get("shares_outstanding") is not None
            else None
        ),
    )


def preview_dcf_from_draft(session_id: str, model_id: str) -> dict:
    entry = _get_draft_entry(session_id, model_id)
    data = entry.get("data") or {}
    inputs = _build_dcf_inputs_from_draft(data)
    company_name = data.get("company_name")
    result = compute_dcf(inputs, company_name=company_name)
    return result.model_dump()


def compute_dcf_from_draft(session_id: str, model_id: str) -> dict:
    entry = _get_draft_entry(session_id, model_id)
    data = dict(entry.get("data") or {})
    inputs = _build_dcf_inputs_from_draft(data)
    company_name = data.get("company_name")
    result = compute_dcf(inputs, company_name=company_name)
    computed_entry = upsert_dcf_computed_from_draft(
        session_id,
        model_id,
        entry,
        result.model_dump(),
    )
    data["computed_model_id"] = computed_entry["id"]
    update_model_entry(session_id, model_id, data=data)
    return {
        "success": True,
        "model_id": computed_entry["id"],
        "model_name": entry.get("name"),
        "draft_model_id": model_id,
        "enterprise_value_millions": result.enterprise_value,
        "equity_value_millions": result.equity_value,
        "price_per_share": result.price_per_share,
        "result": result.model_dump(),
        "updated_existing": computed_entry.get("updated_at") is not None,
    }
