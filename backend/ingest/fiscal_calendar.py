"""Map SEC period-of-report dates to fiscal year / quarter labels."""

from __future__ import annotations

from datetime import date, timedelta


def _safe_fy_end(end_year: int, month: int, day: int) -> date:
    for d in (day, 28, 27):
        try:
            return date(end_year, month, d)
        except ValueError:
            continue
    return date(end_year, month, 28)


def fiscal_year_from_period_end(
    period_end: str | None,
    *,
    fy_end_mmdd: str | None = None,
) -> int | None:
    """Fiscal year label for a reporting period end (10-K / 10-Q)."""
    if not period_end or len(period_end) < 10:
        return None
    try:
        pe = date.fromisoformat(period_end[:10])
    except ValueError:
        return None

    if not fy_end_mmdd or len(fy_end_mmdd) < 4:
        return pe.year

    fy_m = int(fy_end_mmdd[:2])
    fy_d = int(fy_end_mmdd[2:4])

    for end_year in range(pe.year - 1, pe.year + 2):
        fy_end = _safe_fy_end(end_year, fy_m, fy_d)
        prev_fy_end = _safe_fy_end(end_year - 1, fy_m, fy_d)
        window_start = prev_fy_end + timedelta(days=1)
        window_end = fy_end + timedelta(days=7)
        if window_start <= pe <= window_end:
            return end_year
    return pe.year


def fiscal_quarter_from_period_end(
    period_end: str | None,
    *,
    fy_end_mmdd: str | None = None,
) -> str:
    """Return Q1–Q4 for a quarterly period end (approximate from months since FY start)."""
    if not period_end or len(period_end) < 10:
        return "Q1"
    try:
        pe = date.fromisoformat(period_end[:10])
    except ValueError:
        return "Q1"

    if not fy_end_mmdd or len(fy_end_mmdd) < 4:
        month = pe.month
        if month <= 3:
            return "Q1"
        if month <= 6:
            return "Q2"
        if month <= 9:
            return "Q3"
        return "Q4"

    fy_m = int(fy_end_mmdd[:2])
    fy_d = int(fy_end_mmdd[2:4])
    fy = fiscal_year_from_period_end(period_end, fy_end_mmdd=fy_end_mmdd)
    if fy is None:
        return "Q1"
    fy_end = _safe_fy_end(fy, fy_m, fy_d)
    prev_fy_end = _safe_fy_end(fy - 1, fy_m, fy_d)
    fy_start = prev_fy_end + timedelta(days=1)
    days_in = (pe - fy_start).days
    quarter_index = min(3, max(0, days_in // 91))
    return f"Q{quarter_index + 1}"
