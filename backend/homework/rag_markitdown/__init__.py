"""Homework: fetch annual 10-K → MarkItDown → preview (RAG prep, Phase 1)."""

from homework.rag_markitdown.pipeline import ingest_from_sec, ingest_from_upload
from homework.rag_markitdown.schema import IngestResult

__all__ = ["IngestResult", "ingest_from_sec", "ingest_from_upload"]
