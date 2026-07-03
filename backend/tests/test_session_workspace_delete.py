"""Tests for session file/model DELETE API."""

import json

from fastapi.testclient import TestClient

import store as store_module
from api.main import app
from store import create_session, get_model_entry, save_dcf_draft_model, save_file_entry

client = TestClient(app)


def _financials(ticker: str) -> dict:
    return {
        "ticker": ticker,
        "cik": "1",
        "entity_name": ticker,
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "statements": {"income": {"annual": [], "quarterly": []}},
    }


def test_delete_file():
    sid = create_session()
    entry = save_file_entry(
        sid,
        {"name": "AAPL", "type": "financials", "dedup_key": "a1", "data": _financials("AAPL")},
    )
    res = client.delete(f"/api/sessions/{sid}/files/{entry['id']}")
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert client.get(f"/api/sessions/{sid}").json()["files"] == []


def test_delete_model_comparative():
    sid = create_session()
    models_dir = store_module._session_dir(sid) / "models"
    models_dir.mkdir(exist_ok=True)
    model_id = "m-comp-1"
    (models_dir / f"{model_id}.json").write_text(
        json.dumps(
            {
                "id": model_id,
                "name": "KO vs PEP",
                "type": "comparative",
                "created_at": "2026-01-01T00:00:00+00:00",
                "data": {"companies": []},
            }
        ),
        encoding="utf-8",
    )
    res = client.delete(f"/api/sessions/{sid}/models/{model_id}")
    assert res.status_code == 200
    assert get_model_entry(sid, model_id) is None


def test_delete_dcf_draft_also_removes_computed_twin():
    sid = create_session()
    draft = save_dcf_draft_model(
        sid,
        {
            "type": "dcf_draft",
            "ticker": "AAPL",
            "projection_years": 5,
            "reference_history": {"fiscal_years": [], "rows": []},
            "inputs": {},
            "defaults": {},
        },
        name="Test DCF",
    )
    twin_id = "twin-1"
    models_dir = store_module._session_dir(sid) / "models"
    (models_dir / f"{twin_id}.json").write_text(
        json.dumps(
            {
                "id": twin_id,
                "name": "Test DCF",
                "type": "dcf",
                "draft_id": draft["id"],
                "created_at": "2026-01-01T00:00:00+00:00",
                "data": {"draft_id": draft["id"]},
            }
        ),
        encoding="utf-8",
    )
    res = client.delete(f"/api/sessions/{sid}/models/{draft['id']}")
    assert res.status_code == 200
    assert get_model_entry(sid, draft["id"]) is None
    assert get_model_entry(sid, twin_id) is None


def test_delete_file_not_found():
    sid = create_session()
    res = client.delete(f"/api/sessions/{sid}/files/missing")
    assert res.status_code == 404
