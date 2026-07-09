"""Session-scoped state for loop RAG retrieval."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from helper.rag.chunk_ids import filing_key_string
from store import _session_dir, session_exists

RAG_QUERY_STATE_FILE = "rag_query_state.json"
MAX_LOOPS = 15


@dataclass
class ParentChunkRecord:
    parent_id: str
    document_id: str
    ticker: str
    year: int
    doctype: str
    filing_key: str
    chunk_index: int
    char_count: int
    approx_tokens: int
    content: str
    loop: int
    loop_query: str
    winning_sub_id: str
    vector_score: float
    rerank_score: float
    document_source: str | None = None
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def metadata_summary(self) -> dict[str, Any]:
        """Lightweight metadata without full content."""
        d = self.to_dict()
        d.pop("content", None)
        return d

    def citation_short(self) -> str:
        return self.label or f"{self.ticker} · section #{self.chunk_index}"


@dataclass
class RagQueryState:
    original_question: str | None = None
    ticker: str | None = None
    loops_completed: int = 0
    max_loops: int = MAX_LOOPS
    parents: list[ParentChunkRecord] = field(default_factory=list)
    loop_history: list[dict[str, Any]] = field(default_factory=list)
    updated_at: str | None = None

    @property
    def collected_parent_ids(self) -> list[str]:
        return [p.parent_id for p in self.parents]

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_question": self.original_question,
            "ticker": self.ticker,
            "loops_completed": self.loops_completed,
            "max_loops": self.max_loops,
            "parents": [p.to_dict() for p in self.parents],
            "loop_history": self.loop_history,
            "updated_at": self.updated_at,
        }


def _state_path(session_id: str) -> Path:
    return _session_dir(session_id) / RAG_QUERY_STATE_FILE


def load_state(session_id: str) -> RagQueryState | None:
    if not session_exists(session_id):
        return None
    path = _state_path(session_id)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    parents = [ParentChunkRecord(**row) for row in data.get("parents", [])]
    return RagQueryState(
        original_question=data.get("original_question"),
        ticker=data.get("ticker"),
        loops_completed=int(data.get("loops_completed", 0)),
        max_loops=int(data.get("max_loops", MAX_LOOPS)),
        parents=parents,
        loop_history=list(data.get("loop_history", [])),
        updated_at=data.get("updated_at"),
    )


def save_state(session_id: str, state: RagQueryState) -> None:
    state.updated_at = datetime.now(timezone.utc).isoformat()
    path = _state_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")


def clear_state(session_id: str) -> None:
    path = _state_path(session_id)
    if path.is_file():
        path.unlink()


def parent_label(ticker: str, year: int, doctype: str, chunk_index: int) -> str:
    form = "10-K" if doctype.upper().replace("-", "") == "10K" else doctype
    return f"{ticker} · {form} · FY{year} · section #{chunk_index}"


def build_parent_record(
    *,
    parent_row: dict[str, Any],
    loop: int,
    loop_query: str,
    winning_sub_id: str,
    vector_score: float,
    rerank_score: float,
) -> ParentChunkRecord:
    ticker = parent_row["ticker"]
    year = int(parent_row["year"])
    doctype = parent_row["doctype"]
    chunk_index = int(parent_row["chunk_index"])
    return ParentChunkRecord(
        parent_id=parent_row["parent_id"],
        document_id=parent_row["document_id"],
        ticker=ticker,
        year=year,
        doctype=doctype,
        filing_key=filing_key_string(ticker, year, doctype),
        chunk_index=chunk_index,
        char_count=int(parent_row["char_count"]),
        approx_tokens=int(parent_row["approx_tokens"]),
        content=parent_row["content"],
        loop=loop,
        loop_query=loop_query,
        winning_sub_id=winning_sub_id,
        vector_score=vector_score,
        rerank_score=rerank_score,
        document_source=parent_row.get("document_source"),
        label=parent_label(ticker, year, doctype, chunk_index),
    )
