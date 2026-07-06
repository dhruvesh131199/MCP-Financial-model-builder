"""Tests for per-session RAG document index."""

from __future__ import annotations

import store as store_module
from rag_session_store import list_rag_documents, upsert_rag_document
from store import create_session


def test_list_rag_documents_newest_first(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)
    times = iter(
        [
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:01+00:00",
            "2026-07-01T00:00:00+00:00",
            "2026-07-01T00:00:01+00:00",
        ]
    )
    monkeypatch.setattr("rag_session_store._utc_now", lambda: next(times))
    sid = create_session()

    upsert_rag_document(
        sid,
        {
            "filing_key": "AAPL_2024_10K",
            "document_id": "doc-1",
            "ticker": "AAPL",
            "year": 2024,
            "doctype": "10K",
            "label": "AAPL · 10-K · FY2024",
            "source": "sec_annual",
            "status": "ready",
            "from_cache": False,
        },
    )
    upsert_rag_document(
        sid,
        {
            "filing_key": "NVDA_2025_10K",
            "document_id": "doc-2",
            "ticker": "NVDA",
            "year": 2025,
            "doctype": "10K",
            "label": "NVDA · 10-K · FY2025",
            "source": "sec_annual",
            "status": "ready",
            "from_cache": False,
        },
    )

    docs = list_rag_documents(sid)
    assert [d["filing_key"] for d in docs] == ["NVDA_2025_10K", "AAPL_2024_10K"]
