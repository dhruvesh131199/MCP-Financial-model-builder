"""Data models for document ingest (fetch / upload → markdown)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DocumentSource(str, Enum):
    SEC_ANNUAL = "sec_annual"
    MANUAL_UPLOAD = "manual_upload"


class SourceFormat(str, Enum):
    PDF = "pdf"
    HTML = "html"
    OTHER = "other"


class FilingMeta(BaseModel):
    ticker: str | None = None
    entity_name: str | None = None
    cik: str | None = None
    form: str | None = None
    accession_no: str | None = None
    filing_date: str | None = None
    period_of_report: str | None = None
    primary_document: str | None = None


class ItemSection(BaseModel):
    item_id: str
    title: str
    label: str
    char_count: int
    approx_tokens: int
    start_offset: int


class SectionOutline(BaseModel):
    items: list[ItemSection] = Field(default_factory=list)
    preamble: ItemSection | None = None
    total_chars: int = 0
    items_found: int = 0
    warnings: list[str] = Field(default_factory=list)


class SubChunk(BaseModel):
    id: str
    parent_id: str
    content: str
    embedding: list[float] | None = None


class ParentChunk(BaseModel):
    id: str
    ticker: str
    year: int
    doctype: str
    chunk_index: int
    item_id: str | None = None
    item_label: str | None = None
    content: str
    char_count: int
    approx_tokens: int
    subchunks: list[SubChunk] = Field(default_factory=list)


class ChunkPlan(BaseModel):
    document_id: str
    ticker: str
    year: int
    doctype: str
    config: dict[str, int] = Field(default_factory=dict)
    parent_chunks: list[ParentChunk] = Field(default_factory=list)
    parent_count: int = 0
    subchunk_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class IngestResult(BaseModel):
    document_id: str
    source: DocumentSource
    source_format: SourceFormat
    raw_filename: str
    raw_bytes: int
    markdown_chars: int
    markdown_lines: int
    output_dir: str
    raw_path: str
    markdown_path: str
    meta_path: str
    report_html_path: str
    sections_path: str | None = None
    chunks_path: str | None = None
    filing: FilingMeta | None = None
    session_id: str | None = None
    narrative_checks: dict[str, bool] = Field(default_factory=dict)
    section_outline: SectionOutline | None = None
    chunk_plan: ChunkPlan | None = None

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source": self.source.value,
            "source_format": self.source_format.value,
            "raw_filename": self.raw_filename,
            "raw_bytes": self.raw_bytes,
            "markdown_chars": self.markdown_chars,
            "markdown_lines": self.markdown_lines,
            "output_dir": self.output_dir,
            "filing": self.filing.model_dump() if self.filing else None,
            "session_id": self.session_id,
            "narrative_checks": self.narrative_checks,
            "section_outline": (
                self.section_outline.model_dump() if self.section_outline else None
            ),
            "items_found": (
                self.section_outline.items_found if self.section_outline else 0
            ),
            "section_warnings": (
                self.section_outline.warnings if self.section_outline else []
            ),
            "chunk_warnings": (
                self.chunk_plan.warnings if self.chunk_plan else []
            ),
            "parent_count": (
                self.chunk_plan.parent_count if self.chunk_plan else 0
            ),
            "subchunk_count": (
                self.chunk_plan.subchunk_count if self.chunk_plan else 0
            ),
        }
