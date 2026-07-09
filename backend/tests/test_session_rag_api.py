"""Session-scoped RAG REST API tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import store as store_module
from api.main import app
from helper.rag.resolve import RagResolveResult
from rag_session_store import upsert_rag_document

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    import helper.rag.storage as rag_storage

    monkeypatch.setattr(rag_storage, "DATA_DIR", tmp_path)


def _ready_resolve(**overrides) -> RagResolveResult:
    base = dict(
        success=True,
        from_cache=False,
        status="ready",
        document_id="doc-api-1",
        filing_key="AAPL_2025_10K",
        rag_entry_id="entry-1",
        label="AAPL · 10-K · FY2025",
        ticker="AAPL",
        year=2025,
        doctype="10K",
        source="sec_annual",
        parent_count=2,
        subchunk_count=5,
        error=None,
        ingest=None,
    )
    base.update(overrides)
    return RagResolveResult(**base)


@patch("api.session_rag.resolve_or_ingest_sec")
def test_rag_fetch_endpoint(mock_resolve):
    from store import create_session

    sid = create_session()
    mock_resolve.return_value = _ready_resolve()

    res = client.post(
        f"/api/sessions/{sid}/rag/ingest/fetch",
        json={"ticker": "AAPL"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["document_id"] == "doc-api-1"
    assert body["filing_key"] == "AAPL_2025_10K"


@patch("api.session_rag.resolve_or_ingest_sec")
def test_rag_fetch_with_fiscal_year(mock_resolve):
    from store import create_session

    sid = create_session()
    mock_resolve.return_value = _ready_resolve()

    res = client.post(
        f"/api/sessions/{sid}/rag/ingest/fetch",
        json={"ticker": "WMT", "fiscal_year": 2024},
    )
    assert res.status_code == 200
    mock_resolve.assert_called_once()
    assert mock_resolve.call_args.kwargs["fiscal_year"] == 2024


@patch("api.session_rag.resolve_or_ingest_upload")
def test_rag_upload_endpoint(mock_resolve, tmp_path):
    from store import create_session

    sid = create_session()
    mock_resolve.return_value = _ready_resolve(source="manual_upload")

    upload = tmp_path / "sample.html"
    upload.write_text("<html>body</html>", encoding="utf-8")

    with upload.open("rb") as fh:
        res = client.post(
            f"/api/sessions/{sid}/rag/ingest/upload",
            files={"file": ("sample.html", fh, "text/html")},
            data={"ticker": "AAPL", "year": "2025", "doctype": "10K"},
        )
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_workspace_includes_rag_documents():
    from store import create_session, load_workspace

    sid = create_session()
    upsert_rag_document(
        sid,
        {
            "filing_key": "AAPL_2025_10K",
            "document_id": "doc-ws",
            "ticker": "AAPL",
            "year": 2025,
            "doctype": "10K",
            "label": "AAPL · 10-K · FY2025",
            "source": "sec_annual",
            "status": "ready",
            "error": None,
            "from_cache": True,
            "parent_count": 1,
            "subchunk_count": 2,
        },
    )

    res = client.get(f"/api/sessions/{sid}")
    assert res.status_code == 200
    body = res.json()
    assert len(body["rag_documents"]) == 1
    assert body["rag_documents"][0]["document_id"] == "doc-ws"

    ws = load_workspace(sid)
    assert ws is not None
    assert ws["rag_documents"][0]["from_cache"] is True


@patch("api.session_rag._load_chunks_for_document")
def test_chunks_endpoint_returns_plan_shape(mock_load):
    from store import create_session

    sid = create_session()
    upsert_rag_document(
        sid,
        {
            "filing_key": "AAPL_2025_10K",
            "document_id": "doc-chunks",
            "ticker": "AAPL",
            "year": 2025,
            "doctype": "10K",
            "label": "AAPL · 10-K · FY2025",
            "source": "sec_annual",
            "status": "ready",
            "error": None,
            "from_cache": False,
        },
    )
    plan = {
        "document_id": "doc-chunks",
        "ticker": "AAPL",
        "year": 2025,
        "doctype": "10K",
        "config": {},
        "parent_chunks": [],
        "parent_count": 0,
        "subchunk_count": 0,
        "warnings": [],
    }
    mock_load.return_value = plan

    res = client.get(f"/api/sessions/{sid}/rag/documents/doc-chunks/chunks")
    assert res.status_code == 200
    assert res.json() == plan


def test_chunks_endpoint_404_when_not_in_session():
    from store import create_session

    sid = create_session()
    res = client.get(f"/api/sessions/{sid}/rag/documents/missing/chunks")
    assert res.status_code == 404


def test_report_endpoint_serves_html(tmp_path, monkeypatch):
    from store import create_session

    sid = create_session()
    doc_id = "doc-report"
    upsert_rag_document(
        sid,
        {
            "filing_key": "AAPL_2025_10K",
            "document_id": doc_id,
            "ticker": "AAPL",
            "year": 2025,
            "doctype": "10K",
            "label": "AAPL · 10-K · FY2025",
            "source": "sec_annual",
            "status": "ready",
            "error": None,
            "from_cache": False,
            **{
                "report_url": f"/api/sessions/{sid}/rag/documents/{doc_id}/report",
                "raw_url": f"/api/sessions/{sid}/rag/documents/{doc_id}/raw",
                "chunks_url": f"/api/sessions/{sid}/rag/documents/{doc_id}/chunks",
            },
        },
    )
    out_dir = tmp_path / "sessions" / sid / "documents" / doc_id
    out_dir.mkdir(parents=True)
    (out_dir / "meta.json").write_text(
        '{"document_id":"doc-report","raw_filename":"filing.html"}',
        encoding="utf-8",
    )
    (out_dir / "report.html").write_text("<html><body>10-K</body></html>", encoding="utf-8")

    res = client.get(f"/api/sessions/{sid}/rag/documents/{doc_id}/report")
    assert res.status_code == 200
    assert "10-K" in res.text


def test_raw_endpoint_serves_file(tmp_path):
    from store import create_session

    sid = create_session()
    doc_id = "doc-raw"
    upsert_rag_document(
        sid,
        {
            "filing_key": "AAPL_2025_10K",
            "document_id": doc_id,
            "ticker": "AAPL",
            "year": 2025,
            "doctype": "10K",
            "label": "AAPL · 10-K · FY2025",
            "source": "sec_annual",
            "status": "ready",
            "error": None,
            "from_cache": False,
        },
    )
    out_dir = tmp_path / "sessions" / sid / "documents" / doc_id
    out_dir.mkdir(parents=True)
    (out_dir / "meta.json").write_text(
        '{"document_id":"doc-raw","raw_filename":"filing.pdf"}',
        encoding="utf-8",
    )
    (out_dir / "filing.pdf").write_bytes(b"%PDF-1.4")

    res = client.get(f"/api/sessions/{sid}/rag/documents/{doc_id}/raw")
    assert res.status_code == 200
    assert res.content.startswith(b"%PDF")
