"""Pydantic models for hierarchical session statements cache."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ingest.normalize import LineItem

StatementType = Literal["income", "balance", "cashflow"]


class StatementLeaf(BaseModel):
    line_items: list[LineItem] = Field(default_factory=list)
    fetched_at: str | None = None
    ingest_source: str | None = None
    dedup_key: str | None = None


class PeriodCache(BaseModel):
    fiscal_year: int
    fiscal_period: str
    period_end: str | None = None
    filed: str | None = None
    form: str | None = None
    statements: dict[str, StatementLeaf] = Field(default_factory=dict)


class TickerCache(BaseModel):
    ticker: str
    cik: str | None = None
    entity_name: str | None = None
    fy_end_mmdd: str | None = None
    updated_at: str | None = None
    periods: dict[str, PeriodCache] = Field(default_factory=dict)


class StatementsIndex(BaseModel):
    schema_version: int = 1
    updated_at: str | None = None
    tickers: dict[str, TickerCache] = Field(default_factory=dict)


def period_key(fiscal_year: int, fiscal_period: str) -> str:
    fp = (fiscal_period or "FY").strip().upper()
    if fp in ("FY", "ANNUAL", "10-K"):
        return f"FY{fiscal_year}"
    if fp.startswith("Q"):
        return f"{fp}_{fiscal_year}"
    return f"FY{fiscal_year}"
