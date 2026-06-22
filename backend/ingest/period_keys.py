"""Reporting-period keys for SEC companyfacts normalization.

See SEC_NORMALIZE_RULES.md for the business rules these functions implement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

PeriodType = Literal["annual", "quarterly"]

_FRAME_ANNUAL = re.compile(r"^CY(\d{4})$")
_FRAME_QUARTER = re.compile(r"^CY(\d{4})Q([1-4])$")
_FRAME_INSTANT = re.compile(r"^CY(\d{4})Q([1-4])I$")


@dataclass(frozen=True)
class PeriodIdentity:
    """Uniquely identifies one reporting period for bucketing facts."""

    sort_key: str  # end date ISO or synthetic key for stable ordering
    fiscal_year: int
    fiscal_period: str  # FY | Q1 | Q2 | Q3 | Q4
    period_type: PeriodType


def _normalize_fp(row: dict) -> str | None:
    fp = row.get("fp")
    if fp:
        return str(fp)
    form = str(row.get("form") or "")
    if form == "10-K":
        return "FY"
    if form == "10-Q":
        q = row.get("fq")
        if q:
            return str(q)
    return None


def _period_type(fp: str) -> PeriodType:
    return "annual" if fp == "FY" else "quarterly"


def _from_frame(frame: str, fp: str) -> PeriodIdentity | None:
    m = _FRAME_INSTANT.match(frame)
    if m:
        year = int(m.group(1))
        q = f"Q{m.group(2)}"
        return PeriodIdentity(
            sort_key=frame,
            fiscal_year=year,
            fiscal_period=q if fp != "FY" else fp,
            period_type=_period_type(fp if fp != "FY" else "FY"),
        )
    m = _FRAME_QUARTER.match(frame)
    if m:
        year = int(m.group(1))
        q = f"Q{m.group(2)}"
        return PeriodIdentity(
            sort_key=frame,
            fiscal_year=year,
            fiscal_period=q,
            period_type="quarterly",
        )
    m = _FRAME_ANNUAL.match(frame)
    if m:
        year = int(m.group(1))
        return PeriodIdentity(
            sort_key=frame,
            fiscal_year=year,
            fiscal_period="FY",
            period_type="annual",
        )
    return None


def period_identity_from_row(row: dict) -> PeriodIdentity | None:
    """Map one SEC companyfacts row to a reporting period."""
    if row.get("val") is None:
        return None
    fp = _normalize_fp(row)
    if fp is None:
        return None

    end = row.get("end")
    if end:
        end_str = str(end)
        return PeriodIdentity(
            sort_key=end_str,
            fiscal_year=int(end_str[:4]),
            fiscal_period=fp,
            period_type=_period_type(fp),
        )

    frame = row.get("frame")
    if frame:
        parsed = _from_frame(str(frame), fp)
        if parsed is not None:
            return parsed

    fy = row.get("fy")
    if fy is not None:
        fiscal_year = int(fy)
        return PeriodIdentity(
            sort_key=f"{fiscal_year}-{fp}",
            fiscal_year=fiscal_year,
            fiscal_period=fp,
            period_type=_period_type(fp),
        )

    return None


def period_bucket_key(identity: PeriodIdentity) -> tuple[str, str]:
    """Stable dict key: (sort_key, fiscal_period)."""
    return (identity.sort_key, identity.fiscal_period)


def pick_best_fact_row(rows: list[dict], *, fiscal_period: str) -> dict | None:
    """Select one XBRL row for a metric + period — latest filing wins, not largest value."""

    if not rows:
        return None

    def score(row: dict) -> tuple[int, str]:
        form = str(row.get("form") or "")
        if fiscal_period == "FY":
            form_rank = 2 if form == "10-K" else 1 if form == "10-Q" else 0
        else:
            form_rank = 2 if form == "10-Q" else 1 if form == "10-K" else 0
        filed = str(row.get("filed") or "")
        return (form_rank, filed)

    return max(rows, key=score)
