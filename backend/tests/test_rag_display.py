"""Tests for pinned RAG markdown display (rag_display models)."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from services.rag_display_service import pin_rag_display
from store import (
    RAG_DISPLAY_CONTENT_MAX_BYTES,
    create_session,
    delete_model_entry,
    load_workspace,
    save_rag_display_model,
)

client = TestClient(app)


def test_save_rag_display_model():
    sid = create_session()
    entry = save_rag_display_model(
        sid,
        name="AAPL 10-K metrics",
        content_md="## Revenue\n\n| FY | $M |\n|----|-----|\n| 2025 | 391,035 |",
    )
    assert entry["type"] == "rag_display"
    assert entry["name"] == "AAPL 10-K metrics"
    assert "Revenue" in entry["data"]["content_md"]


def test_rag_display_appears_in_workspace():
    sid = create_session()
    entry = save_rag_display_model(sid, name="Metrics", content_md="# Hello")
    ws = load_workspace(sid)
    assert ws is not None
    rag_entries = [m for m in ws["models"] if m["type"] == "rag_display"]
    assert len(rag_entries) == 1
    assert rag_entries[0]["id"] == entry["id"]


def test_rag_display_name_dedupe():
    sid = create_session()
    save_rag_display_model(sid, name="Metrics", content_md="# One")
    second = save_rag_display_model(sid, name="Metrics", content_md="# Two")
    assert second["name"] == "Metrics (2)"


def test_rag_display_rejects_empty_content():
    sid = create_session()
    with pytest.raises(ValueError, match="content"):
        save_rag_display_model(sid, name="Empty", content_md="   ")


def test_rag_display_rejects_oversize_content():
    sid = create_session()
    huge = "x" * (RAG_DISPLAY_CONTENT_MAX_BYTES + 1)
    with pytest.raises(ValueError, match="maximum size"):
        save_rag_display_model(sid, name="Huge", content_md=huge)


def test_delete_rag_display_via_api():
    sid = create_session()
    entry = save_rag_display_model(sid, name="Delete me", content_md="# Bye")
    res = client.delete(f"/api/sessions/{sid}/models/{entry['id']}")
    assert res.status_code == 200
    ws = load_workspace(sid)
    assert ws is not None
    assert not [m for m in ws["models"] if m["id"] == entry["id"]]


def test_pin_rag_display_service_success():
    sid = create_session()
    result = pin_rag_display(
        sid,
        name="NVDA risks",
        content="## Risks\n\nSupply chain exposure.",
    )
    assert result["success"] is True
    assert result["result_id"]
    assert result["name"] == "NVDA risks"


def test_pin_rag_display_service_invalid_session():
    result = pin_rag_display(
        "00000000-0000-0000-0000-000000000000",
        name="X",
        content="# X",
    )
    assert result["error"] == "session_not_found"


def test_delete_model_entry_removes_rag_display():
    sid = create_session()
    entry = save_rag_display_model(sid, name="X", content_md="# X")
    assert delete_model_entry(sid, entry["id"]) is True
    ws = load_workspace(sid)
    assert ws is not None
    assert ws["models"] == []
