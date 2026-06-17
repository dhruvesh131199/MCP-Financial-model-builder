"""Tests for session-scoped store."""

import store as store_module
from store import (
    create_session,
    load_workspace,
    save_dcf_model,
    session_exists,
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


def test_create_session_makes_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()
    assert session_exists(sid)
    assert (store_module.SESSIONS_DIR / sid / "models").is_dir()


def test_save_multiple_models(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()
    save_dcf_model(sid, _payload("Acme", 5))
    save_dcf_model(sid, _payload("Beta", 3))
    ws = load_workspace(sid)
    assert ws is not None
    assert len(ws["models"]) == 2
    assert ws["models"][0]["name"] == "acme_dcf_5"
    assert ws["models"][1]["name"] == "beta_dcf_3"


def test_load_workspace_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()
    ws = load_workspace(sid)
    assert ws["models"] == []
    assert ws["files"] == []
