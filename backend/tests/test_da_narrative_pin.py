"""Tests for Detailed Analysis narrative pin + playbook."""

from __future__ import annotations

from services.da_narrative_store import (
    DA_NARRATIVE_SECTIONS,
    build_narrative_next_actions,
    build_narrative_playbook,
    list_da_narratives,
    save_da_narrative,
    section_content_path,
)
from services.rag_display_service import pin_rag_display
from store import (
    create_session,
    load_workspace,
    save_detailed_analysis_model,
)


def _seed_da(session_id: str, ticker: str = "AAPL") -> dict:
    return save_detailed_analysis_model(
        session_id,
        {
            "data": {
                "ticker": ticker,
                "entity_name": "Apple Inc",
                "cik": "0000320193",
                "fetched_at": "2026-01-01T00:00:00+00:00",
                "source": "test",
                "periods": [],
                "warnings": [],
                "integrity_checks": [],
                "is_bank_style": False,
            },
            "source": {"ticker": ticker},
        },
    )


def test_playbook_has_four_sections_and_five_next_actions():
    playbook = build_narrative_playbook("aapl")
    assert len(playbook) == 4
    assert [r["section_key"] for r in playbook] == [k for k, _ in DA_NARRATIVE_SECTIONS]
    assert "AAPL" in playbook[0]["suggested_query"]

    actions = build_narrative_next_actions("AAPL")
    assert len(actions) == 5
    assert "full_report" in actions[0]
    assert 'section_key="gross_profit"' in actions[1]
    assert 'destination="detailed_analysis"' in actions[1]


def test_pin_default_still_rag_results(tmp_path, monkeypatch):
    import store as store_module

    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()

    result = pin_rag_display(sid, name="Risks", content="# Hello\n\nSources: AAPL")
    assert result["success"] is True
    assert result["destination"] == "rag_results"
    assert "result_id" in result

    ws = load_workspace(sid)
    assert ws is not None
    rag = [m for m in ws["models"] if m["type"] == "rag_display"]
    assert len(rag) == 1
    assert rag[0]["data"]["content_md"].startswith("# Hello")


def test_pin_detailed_analysis_writes_file_and_workspace(tmp_path, monkeypatch):
    import store as store_module

    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()
    _seed_da(sid, "AAPL")

    result = pin_rag_display(
        sid,
        name="Gross profit analysis",
        content="## Margin drivers\n\nSources: AAPL · 10-K",
        destination="detailed_analysis",
        ticker="AAPL",
        section_key="gross_profit",
    )
    assert result["success"] is True
    assert result["destination"] == "detailed_analysis"
    assert result["section_key"] == "gross_profit"

    path = section_content_path(sid, "AAPL", "gross_profit")
    assert path.is_file()
    assert "Margin drivers" in path.read_text(encoding="utf-8")

    listed = list_da_narratives(sid, "AAPL")
    assert len(listed) == 1
    assert listed[0]["section_key"] == "gross_profit"

    ws = load_workspace(sid)
    assert ws is not None
    da = next(m for m in ws["models"] if m["type"] == "detailed_analysis")
    assert "narratives" in da["data"]
    assert da["data"]["narratives"][0]["title"] == "Gross profit analysis"


def test_pin_detailed_analysis_rejects_bad_section(tmp_path, monkeypatch):
    import store as store_module

    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()
    _seed_da(sid, "AAPL")

    result = pin_rag_display(
        sid,
        name="X",
        content="body",
        destination="detailed_analysis",
        ticker="AAPL",
        section_key="not_a_section",
    )
    assert result["error"] == "invalid_input"


def test_pin_detailed_analysis_requires_da_model(tmp_path, monkeypatch):
    import store as store_module

    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()

    result = pin_rag_display(
        sid,
        name="X",
        content="body",
        destination="detailed_analysis",
        ticker="AAPL",
        section_key="cash_flow",
    )
    assert result["error"] == "invalid_input"
    assert "Detailed Analysis" in result["message"]


def test_save_da_narrative_rejects_empty(tmp_path, monkeypatch):
    import store as store_module
    import pytest

    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    sid = create_session()
    _seed_da(sid, "COST")
    with pytest.raises(ValueError, match="content is required"):
        save_da_narrative(sid, "COST", "cash_flow", "   ")
