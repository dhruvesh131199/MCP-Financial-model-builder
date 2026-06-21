"""Normalize SEC companyfacts JSON into FinancialStatements schema."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from ingest.concept_map import LINE_LABELS, STATEMENT_CONCEPTS


class LineItem(BaseModel):
    key: str
    label: str
    value: float
    unit: str = "USD"


class StatementPeriod(BaseModel):
    fiscal_year: int
    fiscal_period: str
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


def _pick_unit_values(fact: dict) -> list[dict]:
    units = fact.get("units") or {}
    for preferred in ("USD", "USD/shares", "shares"):
        if preferred in units:
            return units[preferred]
    for values in units.values():
        if values:
            return values
    return []


def _extract_periods(
    facts: dict,
    concepts: dict[str, list[str]],
) -> tuple[list[StatementPeriod], list[StatementPeriod]]:
    """Group line items by fiscal period."""
    period_map: dict[tuple[int, str], dict[str, float]] = {}
    period_meta: dict[tuple[int, str], dict] = {}

    gaap = (facts.get("facts") or {}).get("us-gaap") or {}

    for key, tags in concepts.items():
        for tag in tags:
            fact = gaap.get(tag)
            if not fact:
                continue
            for row in _pick_unit_values(fact):
                fp = row.get("fp") or "FY"
                fy = row.get("fy")
                val = row.get("val")
                if fy is None or val is None:
                    continue
                bucket_key = (int(fy), str(fp))
                period_map.setdefault(bucket_key, {})[key] = float(val)
                period_meta[bucket_key] = {
                    "filed": row.get("filed"),
                    "form": row.get("form"),
                }
            break

    annual_buckets: dict[tuple[int, str], dict[str, float]] = {}
    quarterly_buckets: dict[tuple[int, str], dict[str, float]] = {}

    for (fy, fp), values in period_map.items():
        if fp == "FY":
            annual_buckets[(fy, fp)] = values
        elif fp in {"Q1", "Q2", "Q3", "Q4"}:
            quarterly_buckets[(fy, fp)] = values

    def _to_periods(
        buckets: dict[tuple[int, str], dict[str, float]],
    ) -> list[StatementPeriod]:
        periods: list[StatementPeriod] = []
        for (fy, fp), items in sorted(
            buckets.items(), key=lambda x: (x[0][0], x[0][1]), reverse=True
        ):
            line_items = [
                LineItem(
                    key=k,
                    label=LINE_LABELS.get(k, k),
                    value=v,
                    unit="USD/shares" if k.startswith("eps") else "USD",
                )
                for k, v in items.items()
            ]
            meta = period_meta.get((fy, fp), {})
            periods.append(
                StatementPeriod(
                    fiscal_year=fy,
                    fiscal_period=fp,
                    filed=meta.get("filed"),
                    form=meta.get("form"),
                    line_items=line_items,
                )
            )
        return periods

    annual = _to_periods(annual_buckets)
    quarterly = _to_periods(quarterly_buckets)

    for period in annual + quarterly:
        ocf = next(
            (li.value for li in period.line_items if li.key == "operating_cash_flow"),
            None,
        )
        capex = next(
            (li.value for li in period.line_items if li.key == "capex"),
            None,
        )
        if ocf is not None and capex is not None:
            period.line_items.append(
                LineItem(
                    key="free_cash_flow",
                    label=LINE_LABELS["free_cash_flow"],
                    value=ocf - abs(capex),
                    unit="USD",
                )
            )

    return annual, quarterly


def normalize_company_facts(
    raw: dict,
    *,
    ticker: str,
    cik: str,
) -> FinancialStatements:
    entity_name = raw.get("entityName") or ticker
    statements: dict[str, StatementSlice] = {}

    for stmt_key, concepts in STATEMENT_CONCEPTS.items():
        annual, quarterly = _extract_periods(raw, concepts)
        statements[stmt_key] = StatementSlice(annual=annual, quarterly=quarterly)

    return FinancialStatements(
        ticker=ticker.upper(),
        cik=str(cik).zfill(10),
        entity_name=entity_name,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        statements=statements,
    )
