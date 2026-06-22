"""Fetch stitched XBRL statements via edgartools XBRLS."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from ingest.edgar_identity import ensure_edgar_identity

STATEMENT_METHODS = {
    "income": "income_statement",
    "balance": "balance_sheet",
    "cashflow": "cashflow_statement",
}


@dataclass
class EdgarFrameSet:
    """Stitched statement DataFrames from edgartools."""

    annual: dict[str, pd.DataFrame] = field(default_factory=dict)
    quarterly: dict[str, pd.DataFrame] = field(default_factory=dict)


@dataclass
class EdgarFetchResult:
    ticker: str
    cik: str
    entity_name: str
    frames: EdgarFrameSet
    warnings: list[str] = field(default_factory=list)


class EdgarFetchError(Exception):
    pass


def _annual_filing_count(max_years: int) -> int:
    """10-Ks to request so XBRLS stitch yields ``max_years`` period columns.

    Each 10-K carries comparative prior-year columns; stitching N filings
    typically produces N-1 distinct fiscal year-ends (e.g. 5 filings → 4 cols).
    Fetch one extra filing, then cap display with ``max_periods=max_years``.
    For a single latest year, one 10-K is enough.
    """
    if max_years <= 1:
        return 1
    return max(1, max_years + 1)


def _to_dataframe(statement: Any) -> pd.DataFrame | None:
    if statement is None:
        return None
    try:
        df = statement.to_dataframe()
    except Exception:
        return None
    if df is None or df.empty:
        return None
    return df


def _stitch_statement(
    xbrls: Any,
    method_name: str,
    *,
    max_periods: int,
) -> pd.DataFrame | None:
    statements = xbrls.statements
    method = getattr(statements, method_name, None)
    if method is None:
        return None
    try:
        rendered = method(max_periods=max_periods, standard=True)
    except TypeError:
        rendered = method(standard=True)
    return _to_dataframe(rendered)


def fetch_edgar_frames(
    *,
    ticker: str,
    cik: str | None = None,
    entity_name: str | None = None,
    max_years: int = 1,
    max_quarterly_periods: int = 4,
    include_annual: bool = True,
    include_quarterly: bool = False,
    statements: list[str] | None = None,
) -> EdgarFetchResult:
    """Download and stitch 10-K / 10-Q XBRL via edgartools."""
    ensure_edgar_identity()

    from edgar import Company
    from edgar.xbrl import XBRLS

    sym = ticker.upper()
    try:
        company = Company(sym if cik is None else int(cik))
    except Exception as exc:
        raise EdgarFetchError(f"Could not load company {sym}: {exc}") from exc

    resolved_ticker = sym
    try:
        t = company.get_ticker()
        if t:
            resolved_ticker = str(t).upper()
    except Exception:
        pass

    name = entity_name or getattr(company, "name", None) or resolved_ticker
    cik_str = str(getattr(company, "cik", cik or "")).zfill(10)

    stmt_keys = statements or list(STATEMENT_METHODS.keys())
    frames = EdgarFrameSet()
    warnings: list[str] = []

    if include_annual:
        try:
            filing_count = _annual_filing_count(max_years)
            k_filings = company.get_filings(form="10-K").head(filing_count)
            if not k_filings:
                warnings.append("No 10-K filings found")
            else:
                xbrls_annual = XBRLS.from_filings(k_filings)
                for key in stmt_keys:
                    method = STATEMENT_METHODS.get(key)
                    if not method:
                        continue
                    df = _stitch_statement(
                        xbrls_annual, method, max_periods=max_years
                    )
                    if df is not None:
                        frames.annual[key] = df
        except Exception as exc:
            raise EdgarFetchError(f"Annual XBRLS stitch failed: {exc}") from exc

    if include_quarterly:
        try:
            q_filings = company.get_filings(form="10-Q").head(max_quarterly_periods)
            if not q_filings:
                warnings.append("No 10-Q filings found")
            else:
                xbrls_quarterly = XBRLS.from_filings(q_filings)
                for key in stmt_keys:
                    method = STATEMENT_METHODS.get(key)
                    if not method:
                        continue
                    df = _stitch_statement(
                        xbrls_quarterly,
                        method,
                        max_periods=max_quarterly_periods,
                    )
                    if df is not None:
                        frames.quarterly[key] = df
        except Exception as exc:
            warnings.append(f"Quarterly XBRLS stitch failed: {exc}")

    if not frames.annual and not frames.quarterly:
        raise EdgarFetchError("No statement data returned from edgartools")

    return EdgarFetchResult(
        ticker=resolved_ticker,
        cik=cik_str,
        entity_name=str(name),
        frames=frames,
        warnings=warnings,
    )
