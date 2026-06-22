"""Comparative analysis orchestration — callable from MCP tools and tests."""

from __future__ import annotations

from typing import Any

from engine.comps import build_comparative_report, extract_fiscal_snapshot
from ingest.normalize import FinancialStatements
from services.market_data import fetch_market_snapshot
from store import (
    get_file_entry,
    merge_comparative_inputs,
    save_comparative_model,
    summarize_comparative_bundle,
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


def handle_run_comparative_analysis(session_id: str) -> dict:
    summary = summarize_comparative_bundle(session_id)
    if not summary["ready"]:
        return {
            "success": False,
            "missing": summary["missing"],
            "next_step": summary["next_step"],
            "message": summary["next_step"],
        }

    fiscal_year = summary["fiscal_year_used"]
    assert fiscal_year is not None

    target_slot = summary["target"]
    peer_slots = summary["peers"] or []
    market_data_errors: list[str] = []

    def _load_company(slot: dict, is_target: bool) -> dict[str, Any]:
        file_id = slot["file_id"]
        entry = get_file_entry(session_id, file_id)
        if not entry:
            raise ValueError(f"SEC file not found for {slot.get('ticker')}")
        financials = FinancialStatements.model_validate(entry["data"]).model_dump()
        snapshot = extract_fiscal_snapshot(financials, fiscal_year)
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
        }

    target = _load_company(target_slot, True)
    peers = [_load_company(p, False) for p in peer_slots]

    report = build_comparative_report(
        target=target,
        peers=peers,
        fiscal_year=fiscal_year,
        fiscal_year_note=summary.get("fiscal_year_note"),
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
        "fiscal_year_note": summary.get("fiscal_year_note"),
        "market_data_errors": report["market_data_errors"],
        "message": (
            f"Comparative report '{entry['name']}' saved for FY{fiscal_year}. "
            f"Companies: {len(report['companies'])}."
        ),
    }
