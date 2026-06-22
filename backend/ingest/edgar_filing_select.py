"""Select exact SEC filings by fiscal year — metadata scan only, no XBRL download."""

from __future__ import annotations

from typing import Any, Iterable

from ingest.fiscal_calendar import fiscal_quarter_from_period_end, fiscal_year_from_period_end

ANNUAL_FORMS = ("10-K", "20-F", "40-F")
QUARTERLY_FORMS = ("10-Q", "6-K")


def _period_end_str(filing: Any) -> str | None:
    period = getattr(filing, "period_of_report", None)
    if not period:
        return None
    text = str(period)[:10]
    return text if len(text) >= 10 else None


def _iter_filings(company: Any, form: str, *, head: int) -> Iterable[Any]:
    try:
        filings = company.get_filings(
            form=form, amendments=False, trigger_full_load=False
        ).head(head)
    except Exception:
        return []
    if filings is None:
        return []
    try:
        return list(filings)
    except TypeError:
        return []


def scan_head_for_targets(
    *,
    target_fiscal_years: set[int],
    quarterly: bool,
    latest_fy: int | None,
    min_fy: int,
) -> int:
    """How many filing rows to scan in metadata (not download XBRL for all)."""
    if not target_fiscal_years:
        return 0
    if quarterly:
        if latest_fy is None:
            span = 4 * max(4, len(target_fiscal_years))
        else:
            span = (latest_fy - min_fy + 1) * 4 + 4
        return min(60, max(12, span))
    span = (latest_fy - min_fy + 1) if latest_fy is not None else len(target_fiscal_years) + 2
    return min(30, max(6, span + 2))


def select_filings_for_fiscal_years(
    company: Any,
    forms: tuple[str, ...],
    target_years: set[int],
    *,
    quarterly: bool,
    fy_end_mmdd: str | None,
    scan_head: int,
) -> list[Any]:
    """Pick the minimal 10-K / 10-Q filings that cover ``target_years``."""
    if quarterly:
        found: dict[tuple[int, str], Any] = {}
        needed_per_fy = 4
    else:
        found_annual: dict[int, Any] = {}

    for form in forms:
        for filing in _iter_filings(company, form, head=scan_head):
            period = _period_end_str(filing)
            if not period:
                continue
            fy = fiscal_year_from_period_end(period, fy_end_mmdd=fy_end_mmdd)
            if fy is None or fy not in target_years:
                continue
            if quarterly:
                q = fiscal_quarter_from_period_end(period, fy_end_mmdd=fy_end_mmdd)
                key = (fy, q)
                if key not in found:
                    found[key] = filing
            elif fy not in found_annual:
                found_annual[fy] = filing

        if quarterly:
            if all(
                sum(1 for (y, _) in found if y == ty) >= 1
                for ty in target_years
            ) and len(found) >= len(target_years):
                # keep scanning until we have reasonable quarter coverage
                if len(found) >= len(target_years) * needed_per_fy:
                    break
        else:
            if found_annual.keys() >= target_years:
                break

    if quarterly:
        selected = list(found.values())
    else:
        selected = [found_annual[y] for y in sorted(target_years) if y in found_annual]

    selected.sort(
        key=lambda f: _period_end_str(f) or "",
        reverse=True,
    )
    return selected


def select_recent_quarterly_filings(
    company: Any,
    forms: tuple[str, ...],
    count: int,
) -> list[Any]:
    """Most recent ``count`` quarterly filings (for trailing-quarter trends)."""
    for form in forms:
        filings = _iter_filings(company, form, head=count)
        if filings:
            return list(filings)
    return []
