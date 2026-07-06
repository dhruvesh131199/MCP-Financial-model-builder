"""Per-session RAG document index (links to global Postgres filings)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from store import _session_dir, session_exists

RAG_INDEX_FILE = "rag_documents.json"


def rag_document_api_urls(session_id: str, document_id: str) -> dict[str, str]:
    base = f"/api/sessions/{session_id}/rag/documents/{document_id}"
    return {
        "report_url": f"{base}/report",
        "raw_url": f"{base}/raw",
        "chunks_url": f"{base}/chunks",
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _index_path(session_id: str) -> Path:
    return _session_dir(session_id) / RAG_INDEX_FILE


def _load_index(session_id: str) -> list[dict[str, Any]]:
    path = _index_path(session_id)
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "documents" in data:
        return list(data["documents"])
    if isinstance(data, list):
        return data
    return []


def _save_index(session_id: str, documents: list[dict[str, Any]]) -> None:
    path = _index_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"documents": documents, "updated_at": _utc_now()}, indent=2),
        encoding="utf-8",
    )


def list_rag_documents(session_id: str) -> list[dict[str, Any]]:
    if not session_exists(session_id):
        return []
    docs = _load_index(session_id)
    return sorted(docs, key=lambda d: d.get("linked_at") or "", reverse=True)


def rag_index_mtime(session_id: str) -> str | None:
    path = _index_path(session_id)
    if not path.is_file():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def find_rag_document(session_id: str, entry_id: str) -> dict[str, Any] | None:
    for doc in _load_index(session_id):
        if doc.get("id") == entry_id:
            return doc
    return None


def find_rag_document_by_document_id(
    session_id: str, document_id: str
) -> dict[str, Any] | None:
    for doc in _load_index(session_id):
        if doc.get("document_id") == document_id:
            return doc
    return None


def upsert_rag_document(session_id: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Insert or update by filing_key."""
    documents = _load_index(session_id)
    filing_key = entry.get("filing_key")
    existing_idx = next(
        (i for i, d in enumerate(documents) if d.get("filing_key") == filing_key),
        None,
    )
    if not entry.get("id"):
        entry["id"] = str(uuid.uuid4())
    entry["linked_at"] = _utc_now()
    if existing_idx is not None:
        documents[existing_idx] = {**documents[existing_idx], **entry}
        out = documents[existing_idx]
    else:
        documents.append(entry)
        out = entry
    _save_index(session_id, documents)
    return out


def record_rag_error(
    session_id: str,
    *,
    label: str,
    ticker: str | None = None,
    year: int | None = None,
    doctype: str | None = None,
    error: str,
    source: str = "manual_upload",
) -> dict[str, Any]:
    filing_key = (
        f"{ticker}_{year}_{doctype}"
        if ticker and year and doctype
        else f"error_{uuid.uuid4().hex[:8]}"
    )
    return upsert_rag_document(
        session_id,
        {
            "filing_key": filing_key,
            "document_id": None,
            "ticker": ticker,
            "year": year,
            "doctype": doctype,
            "label": label,
            "source": source,
            "status": "error",
            "error": error,
            "from_cache": False,
        },
    )
