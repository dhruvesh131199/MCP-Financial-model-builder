"""Build read-only DCF reference history from SEC financials (always 5 fiscal years)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from engine.comps import compute_operating_nwc_from_items, extract_fiscal_snapshot
from ingest.normalize import FinancialStatements

MAX_REFERENCE_YEARS = 5


class DcfReferenceHints(BaseModel):
    """Optional prefill hints for the dashboard editor (all amounts in $M unless noted."""

    base_revenue_m: float | None = None
    shares_outstanding_m: float | None = None
    shares_source: str | None = Field(
        default=None, description="sec | finnhub — where shares hint came from"
    )


class DcfReferenceRow(BaseModel):
    key: str
    label: str
    values: list[float | None]
    format: str = Field(description="currency_m | percent | ratio")


class DcfReferenceHistory(BaseModel):
    ticker: str
    company_name: str | None = None
    fiscal_years: list[int] = Field(description="Newest first, up to 5")
    rows: list[DcfReferenceRow]
    latest_revenue_usd: float | None = None
    hints: DcfReferenceHints = Field(default_factory=DcfReferenceHints)
    units_note: str = "All dollar amounts in $M USD; rates as decimals in API, shown as % in UI."


def ensure_financial_derivations(financials: FinancialStatements) -> FinancialStatements:
    """Run cross-statement EBITDA + period derivations before reference metrics."""
    from ingest.normalize import apply_cross_statement_ebitda_inputs, apply_period_derivations

    apply_cross_statement_ebitda_inputs(financials)
    for slice_ in financials.statements.values():
        for period in list(slice_.annual) + list(slice_.quarterly):
            apply_period_derivations(period)
    return financials


def _annual_fiscal_years(financials: dict, max_years: int = MAX_REFERENCE_YEARS) -> list[int]:
    statements = financials.get("statements") or {}
    income = statements.get("income") or {}
    annual = income.get("annual") or []
    years = sorted({int(p["fiscal_year"]) for p in annual}, reverse=True)
    return years[:max_years]


def _line_value(financials: dict, fiscal_year: int, key: str) -> float | None:
    for slice_ in (financials.get("statements") or {}).values():
        for period in slice_.get("annual") or []:
            if int(period.get("fiscal_year", 0)) != fiscal_year:
                continue
            for li in period.get("line_items") or []:
                if li.get("key") == key:
                    return float(li["value"])
    return None


def _period_line_items(financials: dict, fiscal_year: int) -> dict[str, float]:
    merged: dict[str, float] = {}
    for slice_ in (financials.get("statements") or {}).values():
        for period in slice_.get("annual") or []:
            if int(period.get("fiscal_year", 0)) != fiscal_year:
                continue
            for li in period.get("line_items") or []:
                merged[li["key"]] = float(li["value"])
    return merged


def _da_addback(items: dict[str, float]) -> float | None:
    combined = items.get("depreciation_and_amortization")
    if combined is not None:
        return abs(combined)
    depr = items.get("depreciation")
    amort = items.get("amortization")
    if depr is not None and amort is not None:
        return abs(depr) + abs(amort)
    return None


def _ebitda_from_items(items: dict[str, float]) -> float | None:
    """EBITDA from tagged line or operating income + complete D&A add-back only."""
    if items.get("ebitda") is not None:
        return float(items["ebitda"])
    op = items.get("operating_income")
    da = _da_addback(items)
    if op is not None and da is not None:
        return float(op) + da
    return None


def _effective_tax_rate(financials: dict, fiscal_year: int) -> float | None:
    ibt = _line_value(financials, fiscal_year, "income_before_tax")
    tax = _line_value(financials, fiscal_year, "income_tax_expense")
    if ibt and ibt > 0 and tax is not None:
        return abs(float(tax)) / float(ibt)
    return None


def _safe_div(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return num / den


def build_dcf_reference_history(
    financials: FinancialStatements | dict,
    *,
    max_years: int = MAX_REFERENCE_YEARS,
    hints: DcfReferenceHints | None = None,
) -> DcfReferenceHistory:
    """Build 5-year SEC reference panel rows (independent of DCF forecast length)."""
    if isinstance(financials, FinancialStatements):
        ensure_financial_derivations(financials)
        dump = financials.model_dump()
    else:
        dump = financials

    ticker = str(dump.get("ticker", "")).upper()
    company_name = dump.get("entity_name")

    fiscal_years = _annual_fiscal_years(dump, max_years=max_years)
    if not fiscal_years:
        return DcfReferenceHistory(
            ticker=ticker,
            company_name=company_name,
            fiscal_years=[],
            rows=[],
            latest_revenue_usd=None,
            hints=hints or DcfReferenceHints(),
        )

    revenues_m: list[float | None] = []
    growths: list[float | None] = []
    ebitda_margins: list[float | None] = []
    da_m: list[float | None] = []
    da_pcts: list[float | None] = []
    ebit_m: list[float | None] = []
    nwc_m: list[float | None] = []
    nwc_pcts: list[float | None] = []
    operating_margins: list[float | None] = []
    tax_rates: list[float | None] = []
    capex_pcts: list[float | None] = []
    debt_pct_assets: list[float | None] = []
    net_debt_m: list[float | None] = []
    fcf_margins: list[float | None] = []

    for fy in fiscal_years:
        snap = extract_fiscal_snapshot(dump, fy)
        items = _period_line_items(dump, fy)
        revenue = snap.get("revenue")
        revenues_m.append(revenue / 1_000_000 if revenue else None)
        growths.append(snap.get("revenue_growth_yoy"))

        ebitda = _ebitda_from_items(items)
        da = _da_addback(items)
        ebit = (float(ebitda) - float(da)) if ebitda is not None and da is not None else None
        nwc = compute_operating_nwc_from_items(items)
        if revenue and revenue > 0:
            ebitda_margins.append(float(ebitda) / float(revenue) if ebitda is not None else None)
            da_m.append(float(da) / 1_000_000 if da is not None else None)
            da_pcts.append(_safe_div(da, revenue))
            ebit_m.append(float(ebit) / 1_000_000 if ebit is not None else None)
            nwc_m.append(float(nwc) / 1_000_000 if nwc is not None else None)
            nwc_pcts.append(_safe_div(nwc, revenue))
            operating_margins.append(_safe_div(items.get("operating_income"), revenue))
            capex = snap.get("capex")
            capex_pcts.append(
                abs(float(capex)) / float(revenue) if capex is not None else None
            )
            fcf = snap.get("free_cash_flow")
            fcf_margins.append(float(fcf) / float(revenue) if fcf is not None else None)
        else:
            ebitda_margins.append(None)
            da_m.append(None)
            da_pcts.append(None)
            ebit_m.append(None)
            nwc_m.append(None)
            nwc_pcts.append(None)
            operating_margins.append(None)
            capex_pcts.append(None)
            fcf_margins.append(None)

        nd = snap.get("net_debt")
        net_debt_m.append(float(nd) / 1_000_000 if nd is not None else None)
        tax_rates.append(_effective_tax_rate(dump, fy))

    latest_revenue = revenues_m[0] * 1_000_000 if revenues_m and revenues_m[0] is not None else None
    ref_hints = hints or DcfReferenceHints()
    if ref_hints.base_revenue_m is None and revenues_m and revenues_m[0] is not None:
        ref_hints = ref_hints.model_copy(update={"base_revenue_m": revenues_m[0]})

    rows = [
        DcfReferenceRow(key="revenue", label="Revenue ($M)", values=revenues_m, format="currency_m"),
        DcfReferenceRow(
            key="revenue_growth_yoy",
            label="Rev growth YoY",
            values=growths,
            format="percent",
        ),
        DcfReferenceRow(
            key="ebitda_margin",
            label="EBITDA margin",
            values=ebitda_margins,
            format="percent",
        ),
        DcfReferenceRow(key="da_m", label="Total D&A ($M)", values=da_m, format="currency_m"),
        DcfReferenceRow(
            key="da_pct",
            label="D&A % rev",
            values=da_pcts,
            format="percent",
        ),
        DcfReferenceRow(key="ebit_m", label="EBIT ($M)", values=ebit_m, format="currency_m"),
        DcfReferenceRow(
            key="operating_margin",
            label="Operating margin (if EBITDA N/A)",
            values=operating_margins,
            format="percent",
        ),
        DcfReferenceRow(key="tax_rate", label="Tax rate", values=tax_rates, format="percent"),
        DcfReferenceRow(
            key="capex_pct",
            label="CapEx % rev",
            values=capex_pcts,
            format="percent",
        ),
        DcfReferenceRow(key="nwc_m", label="NWC ($M)", values=nwc_m, format="currency_m"),
        DcfReferenceRow(
            key="nwc_pct",
            label="NWC % rev",
            values=nwc_pcts,
            format="percent",
        ),
        DcfReferenceRow(
            key="net_debt",
            label="Net debt ($M)",
            values=net_debt_m,
            format="currency_m",
        ),
        DcfReferenceRow(
            key="fcf_margin",
            label="FCF margin (historical)",
            values=fcf_margins,
            format="percent",
        ),
    ]

    return DcfReferenceHistory(
        ticker=ticker,
        company_name=company_name,
        fiscal_years=fiscal_years,
        rows=rows,
        latest_revenue_usd=latest_revenue,
        hints=ref_hints,
    )
