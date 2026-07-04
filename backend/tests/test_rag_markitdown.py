"""Tests for RAG MarkItDown homework (no network)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from homework.rag_markitdown.convert import convert_file_to_markdown, markdown_stats
from homework.rag_markitdown.pipeline import ingest_from_upload
from homework.rag_markitdown.resolve import resolve_or_ingest_upload
from homework.rag_markitdown.report_html import build_report_html
from homework.rag_markitdown.schema import DocumentSource, SourceFormat
from homework.rag_markitdown.section_analyze import analyze_sections, approx_tokens

FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "homework"
    / "rag_markitdown"
    / "tests"
    / "fixtures"
    / "sample_10k_excerpt.html"
)
ITEMS_FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "homework"
    / "rag_markitdown"
    / "tests"
    / "fixtures"
    / "sample_10k_items.md"
)

markitdown = pytest.importorskip("markitdown")


def test_convert_html_fixture():
    text = convert_file_to_markdown(FIXTURE)
    lower = text.lower()
    assert "risk factors" in lower
    assert "management" in lower
    chars, lines = markdown_stats(text)
    assert chars > 50
    assert lines >= 1


def test_ingest_from_upload_fixture(tmp_path, monkeypatch):
    out_root = tmp_path / "hw_out"
    monkeypatch.setattr(
        "homework.rag_markitdown.storage.OUTPUT_ROOT",
        out_root,
    )

    result = ingest_from_upload(
        upload_path=FIXTURE,
        original_filename="sample_10k_excerpt.html",
        ticker="DEMO",
        year=2025,
        doctype="10K",
        homework_output=True,
    )

    assert result.source == DocumentSource.MANUAL_UPLOAD
    assert result.source_format == SourceFormat.HTML
    assert Path(result.markdown_path).is_file()
    assert Path(result.report_html_path).is_file()
    assert Path(result.sections_path).is_file()
    assert Path(result.chunks_path).is_file()
    assert result.narrative_checks.get("risk_factors") is True
    assert result.markdown_chars > 0
    assert result.section_outline is not None
    assert result.chunk_plan is not None
    assert result.chunk_plan.ticker == "DEMO"
    assert result.chunk_plan.subchunk_count > 0
    assert result.chunk_plan.parent_chunks[0].id.startswith("DEMO_2025_10K_P_")
    assert result.section_outline is not None
    assert result.section_outline.items_found >= 1
    assert result.chunk_plan.parent_count >= result.section_outline.items_found


def test_mcp_tool_response_shape():
    import importlib.util
    from pathlib import Path
    import sys

    server_path = Path(__file__).resolve().parent.parent / "mcp" / "server.py"

    # We need to make sure mcp package is available
    import types
    sys.modules['mcp.fetch_report'] = types.ModuleType('mcp.fetch_report')
    sys.modules['mcp.fetch_report'].run_fetch_report = lambda *a, **kw: None
    sys.modules['mcp.fetch_report'].ReportType = str

    mod_name = "fm_mcp_server_rag_shape"
    mod = sys.modules.get(mod_name)
    if mod is None:
        spec = importlib.util.spec_from_file_location(mod_name, server_path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

    with patch.object(mod, "resolve_or_create_session", return_value=("sess-1", True)):
        with patch.object(
            mod,
            "run_fetch_report",
            return_value={
                "success": True,
                "report_type": "full_report",
                "results": [
                    {
                        "ticker": "AAPL",
                        "year": 2025,
                        "success": True,
                        "document_id": "doc-1",
                        "filing_key": "AAPL_2025_10K",
                        "from_cache": False,
                    }
                ],
                "errors": [],
                "message": "Fetched 1/1",
            },
        ):
            out = mod.fetch_report(
                report_type="full_report",
                tickers=["AAPL"],
                session_id="sess-1",
            )

    assert out["session_id"] == "sess-1"
    assert out["system_note"] == mod.SYSTEM_NOTE
    assert out["data"]["success"] is True
    assert out["data"]["report_type"] == "full_report"
    assert len(out["data"]["results"]) == 1
    assert out["data"]["results"][0]["document_id"] == "doc-1"


def test_approx_tokens_formula():
    assert approx_tokens(100) == 25
    assert approx_tokens(11) == 3


def test_analyze_sections_items_fixture():
    text = ITEMS_FIXTURE.read_text(encoding="utf-8")
    outline = analyze_sections(text)

    assert outline.preamble is not None
    assert outline.preamble.label == "Preamble (XBRL / cover)"
    assert outline.preamble.char_count > 0
    assert outline.preamble.approx_tokens == approx_tokens(outline.preamble.char_count)

    assert outline.items_found == 3
    item_ids = [i.item_id for i in outline.items]
    assert item_ids == ["1", "1A", "2"]

    item1 = outline.items[0]
    assert "Business" in item1.label
    assert item1.char_count > 200

    item1a = outline.items[1]
    assert item1a.item_id == "1A"
    assert item1a.char_count > 0

    assert any("duplicate" in w.lower() or "dedup" in w.lower() for w in outline.warnings)
    assert outline.total_chars == len(text)


def test_analyze_sections_no_items_fallback():
    outline = analyze_sections("Just a short document with no SEC items.")
    assert outline.items_found == 0
    assert len(outline.items) == 1
    assert outline.items[0].label == "Full document"
    assert outline.warnings


def test_report_html_outline_no_markdown_preview():
    from homework.rag_markitdown.schema import IngestResult

    outline = analyze_sections(ITEMS_FIXTURE.read_text(encoding="utf-8"))
    result = IngestResult(
        document_id="test-doc",
        source=DocumentSource.MANUAL_UPLOAD,
        source_format=SourceFormat.HTML,
        raw_filename="raw_sample.html",
        raw_bytes=100,
        markdown_chars=outline.total_chars,
        markdown_lines=10,
        output_dir="/tmp",
        raw_path="/tmp/raw_sample.html",
        markdown_path="/tmp/converted.md",
        meta_path="/tmp/meta.json",
        report_html_path="/tmp/report.html",
        section_outline=outline,
    )
    html = build_report_html(result, "secret markdown body", outline)
    assert "Section outline" in html
    assert "Open original filing" in html
    assert "secret markdown body" not in html
    assert "Markdown preview" not in html
    assert "Item 1A" in html or "Risk Factors" in html


def test_resolve_upload_appends_session_index(tmp_path, monkeypatch):
    import store as store_module
    from rag_session_store import list_rag_documents
    from store import create_session

    sessions = tmp_path / "sessions"
    monkeypatch.setattr(store_module, "SESSIONS_DIR", sessions)
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    out_root = tmp_path / "hw_out"
    monkeypatch.setattr(
        "homework.rag_markitdown.storage.OUTPUT_ROOT",
        out_root,
    )
    monkeypatch.setattr(
        "homework.rag_markitdown.resolve.get_database_url",
        lambda: None,
    )

    sid = create_session()
    result = resolve_or_ingest_upload(
        session_id=sid,
        upload_path=FIXTURE,
        original_filename="sample_10k_excerpt.html",
        ticker="DEMO",
        year=2025,
        doctype="10K",
    )
    assert result.success is True
    docs = list_rag_documents(sid)
    assert len(docs) == 1
    assert docs[0]["filing_key"] == "DEMO_2025_10K"
    assert docs[0]["status"] == "ready"
    assert docs[0]["document_id"] == result.document_id
