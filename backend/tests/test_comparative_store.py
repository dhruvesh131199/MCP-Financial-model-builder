"""Tests for comparative input bundle and model storage."""

import json

import pytest

import store as store_module
from store import (
    create_session,
    latest_annual_fiscal_year,
    load_comparative_bundle,
    merge_comparative_inputs,
    save_comparative_model,
    save_file_entry,
    summarize_comparative_bundle,
)


def _financials_file(ticker: str, latest_fy: int, extra_years: list[int] | None = None) -> dict:
    years = sorted(set([latest_fy] + (extra_years or [])), reverse=True)
    annual = [
        {
            "fiscal_year": y,
            "fiscal_period": "FY",
            "form": "10-K",
            "line_items": [{"key": "revenue", "label": "Revenue", "value": 1e9, "unit": "USD"}],
        }
        for y in years
    ]
    return {
        "ticker": ticker,
        "cik": "0000000001",
        "entity_name": ticker,
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "statements": {"income": {"annual": annual, "quarterly": []}},
    }


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)


def test_comparative_not_ready_without_file_ids():
    sid = create_session()
    merge_comparative_inputs(
        sid,
        {
            "target": {"ticker": "KO", "company_name": "Coca-Cola"},
            "peers": [{"ticker": "PEP"}, {"ticker": "KDP"}],
        },
    )
    summary = summarize_comparative_bundle(sid)
    assert summary["ready"] is False
    assert any("KO.file_id" in m or m == "KO.file_id" for m in summary["missing"])


def test_reject_more_than_ten_peers():
    sid = create_session()
    peers = [{"ticker": f"P{i}"} for i in range(11)]
    with pytest.raises(ValueError, match="At most 10 peers"):
        merge_comparative_inputs(sid, {"target": {"ticker": "KO"}, "peers": peers})


def test_comparative_ready_with_linked_files():
    sid = create_session()
    ko_file = save_file_entry(
        sid,
        {
            "name": "KO",
            "type": "financials",
            "dedup_key": "KO|test",
            "data": _financials_file("KO", 2024),
        },
    )
    pep_file = save_file_entry(
        sid,
        {
            "name": "PEP",
            "type": "financials",
            "dedup_key": "PEP|test",
            "data": _financials_file("PEP", 2024),
        },
    )
    merge_comparative_inputs(
        sid,
        {
            "target": {"ticker": "KO", "company_name": "Coca-Cola"},
            "peers": [{"ticker": "PEP"}],
        },
    )
    merge_comparative_inputs(sid, {"link": {"ticker": "KO", "file_id": ko_file["id"]}})
    merge_comparative_inputs(sid, {"link": {"ticker": "PEP", "file_id": pep_file["id"]}})
    summary = summarize_comparative_bundle(sid)
    assert summary["ready"] is True
    assert summary["fiscal_year_used"] == 2024


def test_fiscal_year_auto_default_min_of_latest():
    sid = create_session()
    ko_file = save_file_entry(
        sid,
        {"name": "KO", "type": "financials", "dedup_key": "KO|a", "data": _financials_file("KO", 2025)},
    )
    pep_file = save_file_entry(
        sid,
        {"name": "PEP", "type": "financials", "dedup_key": "PEP|b", "data": _financials_file("PEP", 2024)},
    )
    merge_comparative_inputs(
        sid,
        {"target": {"ticker": "KO"}, "peers": [{"ticker": "PEP"}]},
    )
    merge_comparative_inputs(sid, {"link": {"ticker": "KO", "file_id": ko_file["id"]}})
    merge_comparative_inputs(sid, {"link": {"ticker": "PEP", "file_id": pep_file["id"]}})
    summary = summarize_comparative_bundle(sid)
    assert summary["fiscal_year_used"] == 2024
    assert "FY2024" in (summary["fiscal_year_note"] or "")


def test_fiscal_year_user_override():
    sid = create_session()
    ko_file = save_file_entry(
        sid,
        {
            "name": "KO",
            "type": "financials",
            "dedup_key": "KO|c",
            "data": _financials_file("KO", 2024, [2023]),
        },
    )
    pep_file = save_file_entry(
        sid,
        {
            "name": "PEP",
            "type": "financials",
            "dedup_key": "PEP|d",
            "data": _financials_file("PEP", 2024, [2023]),
        },
    )
    merge_comparative_inputs(
        sid,
        {"target": {"ticker": "KO"}, "peers": [{"ticker": "PEP"}], "fiscal_year": 2023},
    )
    merge_comparative_inputs(sid, {"link": {"ticker": "KO", "file_id": ko_file["id"]}})
    merge_comparative_inputs(sid, {"link": {"ticker": "PEP", "file_id": pep_file["id"]}})
    summary = summarize_comparative_bundle(sid)
    assert summary["fiscal_year_used"] == 2023


def test_legacy_inputs_json_migrates_to_dcf_json():
    sid = create_session()
    session_dir = store_module.SESSIONS_DIR / sid
    legacy = {"values": {"wacc": 0.1}, "updated_at": "2026-01-01T00:00:00+00:00"}
    (session_dir / "inputs.json").write_text(json.dumps(legacy), encoding="utf-8")
    bundle = store_module.load_input_bundle(sid)
    assert bundle["values"]["wacc"] == 0.1
    assert (session_dir / "inputs" / "dcf.json").exists()
    assert not (session_dir / "inputs.json").exists()


def test_save_comparative_model():
    sid = create_session()
    entry = save_comparative_model(
        sid,
        {
            "target": {"ticker": "KO"},
            "peers": [{"ticker": "PEP"}],
            "fiscal_year_used": 2024,
            "companies": [],
        },
    )
    assert entry["type"] == "comparative"
    assert "comps" in entry["name"]


def test_latest_annual_fiscal_year_prefers_10k():
    data = _financials_file("X", 2024)
    assert latest_annual_fiscal_year(data) == 2024


def test_load_comparative_bundle_empty():
    sid = create_session()
    bundle = load_comparative_bundle(sid)
    assert bundle["model_type"] == "comparative"
    assert bundle["target"] is None
    assert bundle["peers"] == []
