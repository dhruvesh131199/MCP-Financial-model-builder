"""Normalize SEC companyfacts JSON into FinancialStatements schema."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from ingest.concept_map import LINE_LABELS, STATEMENT_METRIC_ORDER
from ingest.coverage import CoverageEntry, build_coverage_report
from ingest.metric_catalog import METRICS_BY_KEY, metrics_for_statement
from ingest.period_keys import (
    PeriodIdentity,
    period_bucket_key,
    period_identity_from_row,
    pick_best_fact_row,
)


class LineItem(BaseModel):
    key: str
    label: str
    value: float
    unit: str = "USD"
    source: str = "xbrl"  # xbrl | derived
    xbrl_tag: str | None = None
    derived_from: list[str] | None = None


class StatementPeriod(BaseModel):
    fiscal_year: int
    fiscal_period: str
    period_end: str | None = None
    filed: str | None = None
    form: str | None = None
    line_items: list[LineItem]


class StatementSlice(BaseModel):
    annual: list[StatementPeriod] = Field(default_factory=list)
    quarterly: list[StatementPeriod] = Field(default_factory=list)


class FinancialStatements(BaseModel):
    ticker: str
    cik: str
    entity_name: str
    fetched_at: str
    statements: dict[str, StatementSlice]
    fetch_scope: list[str] = Field(
        default_factory=lambda: ["income", "balance", "cashflow"]
    )
    coverage: dict[str, CoverageEntry] | None = None
    ingest_source: str | None = None  # edgartools | companyfacts


def _unit_for_metric(key: str) -> str:
    m = METRICS_BY_KEY.get(key)
    return m.unit if m else "USD"


def _pick_unit_values(fact: dict, preferred_units: tuple[str, ...]) -> list[dict]:
    units = fact.get("units") or {}
    for preferred in preferred_units:
        if preferred in units:
            return units[preferred]
    for values in units.values():
        if values:
            return values
    return []


def _extract_periods(
    facts: dict,
    statement: str,
    *,
    derive: bool = True,
) -> tuple[list[StatementPeriod], list[StatementPeriod]]:
    """Pass 1–3: collect XBRL facts by reporting period, then assemble statement rows."""
    BucketKey = tuple[str, str]
    period_values: dict[BucketKey, dict[str, float]] = {}
    period_meta: dict[BucketKey, dict] = {}
    period_provenance: dict[BucketKey, dict[str, dict[str, Any]]] = {}
    period_identities: dict[BucketKey, PeriodIdentity] = {}

    all_facts = facts.get("facts") or {}

    for metric in metrics_for_statement(statement):  # type: ignore[arg-type]
        key = metric.key
        for alias in metric.aliases:
            ns_facts = all_facts.get(alias.namespace) or {}
            fact = ns_facts.get(alias.tag)
            if not fact:
                continue
            preferred = (metric.unit, "USD", "USD/shares", "shares")
            rows_by_bucket: dict[BucketKey, list[dict]] = {}
            for row in _pick_unit_values(fact, preferred):
                identity = period_identity_from_row(row)
                if identity is None:
                    continue
                bucket = period_bucket_key(identity)
                rows_by_bucket.setdefault(bucket, []).append(row)
                period_identities.setdefault(bucket, identity)

            for bucket_key, candidates in rows_by_bucket.items():
                if key in period_values.get(bucket_key, {}):
                    continue
                fp = period_identities[bucket_key].fiscal_period
                best = pick_best_fact_row(candidates, fiscal_period=fp)
                if best is None:
                    continue
                period_values.setdefault(bucket_key, {})[key] = float(best["val"])
                period_provenance.setdefault(bucket_key, {})[key] = {
                    "source": "xbrl",
                    "xbrl_tag": alias.tag,
                    "namespace": alias.namespace,
                }
                existing_filed = period_meta.get(bucket_key, {}).get("filed")
                new_filed = best.get("filed")
                if not existing_filed or (new_filed and str(new_filed) > str(existing_filed)):
                    period_meta[bucket_key] = {
                        "filed": new_filed,
                        "form": best.get("form"),
                    }

    annual_buckets: dict[BucketKey, dict[str, float]] = {}
    quarterly_buckets: dict[BucketKey, dict[str, float]] = {}

    for bucket_key, values in period_values.items():
        identity = period_identities[bucket_key]
        if identity.period_type == "annual":
            annual_buckets[bucket_key] = values
        else:
            quarterly_buckets[bucket_key] = values

    def _to_periods(
        buckets: dict[BucketKey, dict[str, float]],
    ) -> list[StatementPeriod]:
        periods: list[StatementPeriod] = []
        order = STATEMENT_METRIC_ORDER.get(statement, ())

        def _sort_key(item: tuple[BucketKey, dict[str, float]]) -> tuple[int, str, str]:
            bucket_key, _ = item
            identity = period_identities[bucket_key]
            return (identity.fiscal_year, identity.fiscal_period, identity.sort_key)

        for bucket_key, items in sorted(buckets.items(), key=_sort_key, reverse=True):
            identity = period_identities[bucket_key]
            prov = period_provenance.get(bucket_key, {})
            ordered_keys = [k for k in order if k in items]
            extra_keys = [k for k in items if k not in ordered_keys]
            line_items = [
                LineItem(
                    key=k,
                    label=LINE_LABELS.get(k, k),
                    value=items[k],
                    unit=_unit_for_metric(k),
                    source=prov.get(k, {}).get("source", "xbrl"),
                    xbrl_tag=prov.get(k, {}).get("xbrl_tag"),
                )
                for k in ordered_keys + extra_keys
            ]
            meta = period_meta.get(bucket_key, {})
            periods.append(
                StatementPeriod(
                    fiscal_year=identity.fiscal_year,
                    fiscal_period=identity.fiscal_period,
                    filed=meta.get("filed"),
                    form=meta.get("form"),
                    line_items=line_items,
                )
            )
        return periods

    annual = _to_periods(annual_buckets)
    quarterly = _to_periods(quarterly_buckets)

    for period in annual + quarterly:
        if derive:
            apply_period_derivations(period)

    return annual, quarterly


def _line_item(period: StatementPeriod, key: str) -> LineItem | None:
    for li in period.line_items:
        if li.key == key:
            return li
    return None


def _line_value(period: StatementPeriod, key: str) -> float | None:
    li = _line_item(period, key)
    return li.value if li else None


def _da_addback_for_ebitda(period: StatementPeriod) -> tuple[float, list[str]] | None:
    """Complete D&A add-back only — never treat a missing leg as zero."""
    combined = _line_value(period, "depreciation_and_amortization")
    if combined is not None:
        return abs(combined), ["depreciation_and_amortization"]
    depr = _line_value(period, "depreciation")
    amort = _line_value(period, "amortization")
    if depr is not None and amort is not None:
        return abs(depr) + abs(amort), ["depreciation", "amortization"]
    return None


def _ebitda_insert_after_key(period: StatementPeriod) -> str:
    for key in (
        "depreciation_and_amortization",
        "amortization",
        "depreciation",
        "operating_income",
    ):
        if _line_item(period, key) is not None:
            return key
    return "operating_income"


def apply_cross_statement_ebitda_inputs(financials: FinancialStatements) -> None:
    """Copy cash-flow D&A onto income when income lacks a complete add-back."""
    income = financials.statements.get("income")
    cashflow = financials.statements.get("cashflow")
    if not income or not cashflow:
        return

    def _index(periods: list[StatementPeriod]) -> dict[tuple[int, str, str | None], StatementPeriod]:
        return {
            (p.fiscal_year, p.fiscal_period, p.period_end): p for p in periods
        }

    cf_maps = (_index(cashflow.annual), _index(cashflow.quarterly))
    income_slices = (income.annual, income.quarterly)

    for income_periods, cf_map in zip(income_slices, cf_maps, strict=True):
        for period in income_periods:
            if _da_addback_for_ebitda(period) is not None:
                continue
            cf_period = cf_map.get((period.fiscal_year, period.fiscal_period, period.period_end))
            if cf_period is None:
                cf_period = cf_map.get((period.fiscal_year, period.fiscal_period, None))
            if cf_period is None:
                for key, candidate in cf_map.items():
                    if key[0] == period.fiscal_year and key[1] == period.fiscal_period:
                        cf_period = candidate
                        break
            if cf_period is None:
                continue
            cf_da = _line_value(cf_period, "depreciation_and_amortization")
            if cf_da is None:
                continue
            if _line_item(period, "depreciation_and_amortization") is not None:
                continue
            _insert_line_item(
                period,
                LineItem(
                    key="depreciation_and_amortization",
                    label=LINE_LABELS["depreciation_and_amortization"],
                    value=cf_da,
                    unit="USD",
                    source="derived",
                    derived_from=["cashflow:depreciation_and_amortization"],
                ),
                after_key="operating_income",
            )
            apply_period_derivations(period)


def _insert_line_item(period: StatementPeriod, item: LineItem, after_key: str | None = None) -> None:
    if after_key:
        for i, li in enumerate(period.line_items):
            if li.key == after_key:
                period.line_items.insert(i + 1, item)
                return
    period.line_items.append(item)


def apply_period_derivations(period: StatementPeriod) -> None:
    """Public wrapper — derive canonical lines when components exist."""
    _append_derived_line_items(period)


def _append_derived_line_items(period: StatementPeriod) -> None:
    """Derive canonical lines when components exist; never invent without inputs."""
    if _line_item(period, "revenue") is None:
        gross = _line_value(period, "gross_profit")
        cogs = _line_value(period, "cost_of_revenue")
        if gross is not None and cogs is not None:
            period.line_items.insert(
                0,
                LineItem(
                    key="revenue",
                    label=LINE_LABELS["revenue"],
                    value=gross + abs(cogs),
                    unit="USD",
                    source="derived",
                    derived_from=["gross_profit", "cost_of_revenue"],
                ),
            )

    if _line_item(period, "gross_profit") is None:
        rev = _line_value(period, "revenue")
        cogs = _line_value(period, "cost_of_revenue")
        if rev is not None and cogs is not None:
            _insert_line_item(
                period,
                LineItem(
                    key="gross_profit",
                    label=LINE_LABELS["gross_profit"],
                    value=rev - abs(cogs),
                    unit="USD",
                    source="derived",
                    derived_from=["revenue", "cost_of_revenue"],
                ),
                after_key="cost_of_revenue",
            )

    if _line_item(period, "net_income") is None:
        eps = _line_value(period, "eps_diluted")
        shares = _line_value(period, "weighted_avg_shares_diluted")
        if eps is not None and shares is not None:
            _insert_line_item(
                period,
                LineItem(
                    key="net_income",
                    label=LINE_LABELS["net_income"],
                    value=eps * shares,
                    unit="USD",
                    source="derived",
                    derived_from=["eps_diluted", "weighted_avg_shares_diluted"],
                ),
                after_key="eps_diluted",
            )

    if _line_item(period, "eps_diluted") is None:
        ni = _line_value(period, "net_income")
        shares = _line_value(period, "weighted_avg_shares_diluted")
        if ni is not None and shares and shares > 0:
            _insert_line_item(
                period,
                LineItem(
                    key="eps_diluted",
                    label=LINE_LABELS["eps_diluted"],
                    value=ni / shares,
                    unit="USD/shares",
                    source="derived",
                    derived_from=["net_income", "weighted_avg_shares_diluted"],
                ),
                after_key="net_income",
            )

    if _line_item(period, "shares_outstanding") is None:
        diluted = _line_value(period, "weighted_avg_shares_diluted")
        if diluted is not None:
            _insert_line_item(
                period,
                LineItem(
                    key="shares_outstanding",
                    label=LINE_LABELS["shares_outstanding"],
                    value=diluted,
                    unit="shares",
                    source="derived",
                    derived_from=["weighted_avg_shares_diluted"],
                ),
            )

    if _line_item(period, "ebitda") is None:
        op = _line_value(period, "operating_income")
        da = _da_addback_for_ebitda(period)
        if op is not None and da is not None:
            addback, da_keys = da
            _insert_line_item(
                period,
                LineItem(
                    key="ebitda",
                    label=LINE_LABELS["ebitda"],
                    value=op + addback,
                    unit="USD",
                    source="derived",
                    derived_from=["operating_income", *da_keys],
                ),
                after_key=_ebitda_insert_after_key(period),
            )

    ocf = _line_value(period, "operating_cash_flow")
    capex = _line_value(period, "capex")
    if ocf is not None and capex is not None and _line_item(period, "free_cash_flow") is None:
        _insert_line_item(
            period,
            LineItem(
                key="free_cash_flow",
                label=LINE_LABELS["free_cash_flow"],
                value=ocf - abs(capex),
                unit="USD",
                source="derived",
                derived_from=["operating_cash_flow", "capex"],
            ),
        )

    if _line_item(period, "total_debt") is None:
        st = _line_value(period, "short_term_debt")
        lt = _line_value(period, "long_term_debt")
        if st is not None and lt is not None:
            _insert_line_item(
                period,
                LineItem(
                    key="total_debt",
                    label=LINE_LABELS["total_debt"],
                    value=st + lt,
                    unit="USD",
                    source="derived",
                    derived_from=["short_term_debt", "long_term_debt"],
                ),
                after_key="long_term_debt",
            )


def normalize_company_facts(
    raw: dict,
    *,
    ticker: str,
    cik: str,
    coverage_fiscal_year: int | None = None,
    derive: bool = True,
) -> FinancialStatements:
    entity_name = raw.get("entityName") or ticker
    statements: dict[str, StatementSlice] = {}

    for stmt_key in ("income", "balance", "cashflow"):
        annual, quarterly = _extract_periods(raw, stmt_key, derive=derive)
        statements[stmt_key] = StatementSlice(annual=annual, quarterly=quarterly)

    result = FinancialStatements(
        ticker=ticker.upper(),
        cik=str(cik).zfill(10),
        entity_name=entity_name,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        statements=statements,
        ingest_source="companyfacts",
    )
    if derive:
        apply_cross_statement_ebitda_inputs(result)

    dump = result.model_dump()
    fy = coverage_fiscal_year
    if fy is None:
        income = statements.get("income")
        if income and income.annual:
            fy = income.annual[0].fiscal_year
    if fy is not None:
        cov = build_coverage_report(dump, fy)
        result = result.model_copy(update={"coverage": cov})

    return result
