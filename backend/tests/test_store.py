"""Tests for session-scoped store."""

import pytest

import store as store_module
from store import (
    build_dcf_inputs_from_bundle,
    create_session,
    load_workspace,
    merge_model_inputs,
    save_dcf_model,
    session_exists,
    summarize_input_bundle,
)


def _payload(company: str = "Acme", years: int = 5) -> dict:
    return {
        "company_name": company,
        "inputs": {"projection_years": years},
        "enterprise_value": 100.0,
        "years": [],
        "terminal_value": 0,
        "pv_terminal": 0,
    }


def _full_inputs() -> dict:
    return {
        "base_revenue": 100.0,
        "revenue_growth": 0.10,
        "ebitda_margin": 0.25,
        "tax_rate": 0.21,
        "capex_pct": 0.03,
        "nwc_pct": 0.02,
        "wacc": 0.10,
        "terminal_growth": 0.02,
        "projection_years": 5,
    }


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)


def test_create_session_makes_folder():
    sid = create_session()
    assert session_exists(sid)
    assert (store_module.SESSIONS_DIR / sid / "models").is_dir()


def test_save_multiple_models():
    sid = create_session()
    save_dcf_model(sid, _payload("Acme", 5))
    save_dcf_model(sid, _payload("Beta", 3))
    ws = load_workspace(sid)
    assert ws is not None
    assert len(ws["models"]) == 2


def test_input_bundle_missing_fields():
    sid = create_session()
    summary = merge_model_inputs(sid, {"wacc": 0.10})
    assert summary["ready"] is False
    assert "base_revenue" in summary["missing_required"]
    assert summary["filled"]["wacc"] == 0.10


def test_input_bundle_ready():
    sid = create_session()
    summary = merge_model_inputs(sid, _full_inputs())
    assert summary["ready"] is True
    assert summary["missing_required"] == []


def test_input_bundle_merge_partial():
    sid = create_session()
    merge_model_inputs(sid, {"wacc": 0.10, "base_revenue": 100.0})
    summary = merge_model_inputs(sid, {"terminal_growth": 0.02, "tax_rate": 0.21})
    assert summary["filled"]["wacc"] == 0.10
    assert summary["filled"]["base_revenue"] == 100.0
    assert summary["ready"] is False


def test_build_dcf_inputs_rejects_incomplete():
    sid = create_session()
    merge_model_inputs(sid, {"wacc": 0.10})
    with pytest.raises(ValueError, match="Missing required"):
        build_dcf_inputs_from_bundle(sid)


def test_build_dcf_inputs_when_ready():
    sid = create_session()
    merge_model_inputs(sid, _full_inputs())
    inputs = build_dcf_inputs_from_bundle(sid)
    assert inputs.base_revenue == 100.0
    assert inputs.wacc == 0.10
