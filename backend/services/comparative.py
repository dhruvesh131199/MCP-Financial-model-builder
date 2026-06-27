"""Comparative analysis orchestration — callable from MCP tools and tests."""

from __future__ import annotations

from typing import Any

from engine.comps import build_comparative_report, extract_fiscal_snapshot
from ingest.normalize import FinancialStatements
from services.market_data import fetch_market_snapshot
from services.sec_financials import fetch_and_cache_statements
from services.statements_store import compute_fetch_gaps
from store import (
    apply_comparative_file_links,
    get_file_entry,
    latest_annual_fiscal_year,
    load_comparative_bundle,
    merge_comparative_inputs,
    save_comparative_model,
    summarize_comparative_bundle,
)


COMPARATIVE_SEC_MAX_YEARS = 2
COMPARATIVE_STATEMENTS = ["income", "balance", "cashflow"]


def _annual_income_years(financials_data: dict) -> set[int]:
    income = (financials_data.get("statements") or {}).get("income") or {}
    return {int(p["fiscal_year"]) for p in income.get("annual") or []}


def _linked_file_has_comparative_years(session_id: str, slot: dict) -> bool:
    """True when linked Files entry has latest FY plus a prior year for YoY growth."""
    file_id = slot.get("file_id")
    if not file_id:
        return False
    entry = get_file_entry(session_id, file_id)
    if not entry:
        return False
    years = _annual_income_years(entry.get("data") or {})
    if len(years) < 2:
        return False
    latest = max(years)
    return any(y < latest for y in years)


def comparative_fetch_gaps(session_id: str, ticker: str) -> list:
    """Annual gaps for last N years — incremental fetch skips years already cached."""
    return compute_fetch_gaps(
        session_id,
        ticker,
        max_years=COMPARATIVE_SEC_MAX_YEARS,
        include_annual=True,
        include_quarterly=False,
        statements=COMPARATIVE_STATEMENTS,
    )


def handle_set_comparative_inputs(session_id: str, values: dict[str, Any]) -> dict:
    if not values:
        return {
            "error": "values object is required",
            "example": {
                "target": {"ticker": "KO", "company_name": "Coca-Cola"},
                "peers": [{"ticker": "PEP", "company_name": "PepsiCo"}],
            },
        }
    try:
        summary = merge_comparative_inputs(session_id, values)
    except ValueError as exc:
        return {"error": str(exc)}
    except KeyError:
        return {"error": "Session not found. Call start_session first."}

    msg = summary["next_step"]
    if summary["ready"]:
        msg = (
            f"Comparative inputs ready (FY{summary['fiscal_year_used']}). "
            "Call run_comparative_analysis()."
        )
    return {**summary, "message": msg}


def ensure_comparative_sec_files(session_id: str) -> None:
    """Fetch missing SEC periods (last 2 annual years) and auto-link ticker Files."""
    apply_comparative_file_links(session_id)
    bundle = load_comparative_bundle(session_id)
    slots: list[dict] = []
    if bundle.get("target"):
        slots.append(bundle["target"])
    slots.extend(bundle.get("peers") or [])

    for slot in slots:
        ticker = slot.get("ticker")
        if not ticker:
            continue
        if _linked_file_has_comparative_years(session_id, slot):
            continue
        if not comparative_fetch_gaps(session_id, ticker):
            continue
        try:
            fetch_and_cache_statements(
                session_id,
                ticker=ticker,
                max_years=COMPARATIVE_SEC_MAX_YEARS,
                include_annual=True,
                include_quarterly=False,
                statements=COMPARATIVE_STATEMENTS,
            )
        except (ValueError, OSError, RuntimeError):
            continue

    apply_comparative_file_links(session_id)


def handle_run_comparative_analysis(session_id: str) -> dict:
    ensure_comparative_sec_files(session_id)
    summary = summarize_comparative_bundle(session_id)
    if not summary["ready"]:
        return {
            "success": False,
            "missing": summary["missing"],
            "next_step": summary["next_step"],
            "message": summary["next_step"],
        }

    bundle = load_comparative_bundle(session_id)
    explicit_fy = bundle.get("fiscal_year")

    target_slot = summary["target"]
    peer_slots = summary["peers"] or []
    market_data_errors: list[str] = []

    def _fiscal_year_for(financials: dict) -> int:
        if explicit_fy is not None:
            return int(explicit_fy)
        latest = latest_annual_fiscal_year(financials)
        if latest is None:
            raise ValueError("No annual income periods in SEC file")
        return latest

    def _load_company(slot: dict, is_target: bool) -> dict[str, Any]:
        file_id = slot["file_id"]
        entry = get_file_entry(session_id, file_id)
        if not entry:
            raise ValueError(f"SEC file not found for {slot.get('ticker')}")
        financials = FinancialStatements.model_validate(entry["data"]).model_dump()
        fy = _fiscal_year_for(financials)
        snapshot = extract_fiscal_snapshot(financials, fy)
        sec_shares = snapshot.get("shares_outstanding")
        market = fetch_market_snapshot(
            slot["ticker"],
            sec_shares_outstanding=sec_shares,
        )
        if not market.get("ok"):
            market_data_errors.append(slot["ticker"])
        return {
            "ticker": slot["ticker"],
            "company_name": slot.get("company_name") or financials.get("entity_name"),
            "is_target": is_target,
            "financials": financials,
            "market_data": market,
            "snapshot": snapshot,
            "fiscal_year_used": fy,
        }

    target = _load_company(target_slot, True)
    peers = [_load_company(p, False) for p in peer_slots]

    fiscal_year = int(explicit_fy) if explicit_fy is not None else target["fiscal_year_used"]
    fiscal_year_note = summary.get("fiscal_year_note")

    report = build_comparative_report(
        target=target,
        peers=peers,
        fiscal_year=fiscal_year,
        fiscal_year_note=fiscal_year_note,
    )
    report["market_data_errors"] = list(
        set(report.get("market_data_errors", []) + market_data_errors)
    )

    entry = save_comparative_model(session_id, report)

    return {
        "success": True,
        "model_id": entry["id"],
        "model_name": entry["name"],
        "fiscal_year_used": fiscal_year,
        "fiscal_year_note": fiscal_year_note,
        "market_data_errors": report["market_data_errors"],
        "message": (
            f"Comparative report '{entry['name']}' saved for FY{fiscal_year}. "
            f"Companies: {len(report['companies'])}."
        ),
    }
