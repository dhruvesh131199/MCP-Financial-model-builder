"""Map edgartools standard_concept + raw XBRL tags to canonical metric keys."""

from __future__ import annotations

from ingest.metric_catalog import METRICS_BY_KEY

# standard_concept string → canonical key (first match wins per period in adapter)
STANDARD_CONCEPT_TO_KEY: dict[str, str] = {
    "Revenue": "revenue",
    "CostOfGoodsAndServicesSold": "cost_of_revenue",
    "GrossProfit": "gross_profit",
    "ResearchAndDevelopmentExpenses": "research_and_development",
    "SellingGeneralAndAdminExpenses": "selling_general_admin",
    "OperatingIncomeLoss": "operating_income",
    "DepreciationExpense": "depreciation",
    "DepreciationAndAmortization": "depreciation_and_amortization",
    "AmortizationOfIntangibles": "amortization",
    "InterestExpense": "interest_expense",
    "PretaxIncomeLoss": "income_before_tax",
    "IncomeTaxes": "income_tax_expense",
    "NetIncome": "net_income",
    "ProfitLoss": "net_income",
    "SharesAverage": "weighted_avg_shares_basic",
    "SharesFullyDilutedAverage": "weighted_avg_shares_diluted",
    "SharesYearEnd": "shares_outstanding",
    "CashAndMarketableSecurities": "cash",
    "ShortTermInvestments": "short_term_investments",
    "Assets": "total_assets",
    "Liabilities": "total_liabilities",
    "CommonEquity": "stockholders_equity",
    "AllEquityBalance": "stockholders_equity",
    "AllEquityBalanceIncludingMinorityInterest": "stockholders_equity",
    "ShortTermDebt": "short_term_debt",
    "LongTermDebt": "long_term_debt",
    "CapitalExpenses": "capex",
    "NetCashFromOperatingActivities": "operating_cash_flow",
}

# When edgartools maps multiple XBRL rows to one standard_concept, pick — never sum.
STANDARD_CONCEPT_TAG_PRIORITY: dict[str, tuple[str, ...]] = {
    "CostOfGoodsAndServicesSold": (
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
        "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
    ),
}


def tag_priority_rank(standard_concept: str, raw_concept: str | None) -> int:
    """Lower rank = preferred when several rows share a standard_concept."""
    tag = _strip_namespace(str(raw_concept or ""))
    priorities = STANDARD_CONCEPT_TAG_PRIORITY.get(standard_concept, ())
    try:
        return priorities.index(tag)
    except ValueError:
        return len(priorities)


# When multiple concepts map to the same key, prefer this order.
CONCEPT_PRIORITY: dict[str, tuple[str, ...]] = {
    "net_income": ("NetIncome", "ProfitLoss"),
    "stockholders_equity": (
        "AllEquityBalance",
        "AllEquityBalanceIncludingMinorityInterest",
        "CommonEquity",
    ),
}

# Raw XBRL tag suffix (after us-gaap_ / dei_) → canonical key
RAW_TAG_TO_KEY: dict[str, str] = {}
for metric in METRICS_BY_KEY.values():
    for alias in metric.aliases:
        RAW_TAG_TO_KEY[alias.tag] = metric.key

# Extra tags seen in filings but not always standardized
RAW_TAG_TO_KEY.setdefault(
    "NetCashProvidedByUsedInOperatingActivities",
    "operating_cash_flow",
)


def _strip_namespace(concept: str) -> str:
    text = str(concept or "").strip()
    for prefix in ("us-gaap_", "dei_", "srt_"):
        if text.startswith(prefix):
            return text[len(prefix) :]
    return text


# Cash-flow stitch maps combined D&A to a single canonical key.
CASHFLOW_STANDARD_CONCEPT_OVERRIDES: dict[str, str] = {
    "DepreciationExpense": "depreciation_and_amortization",
}


def standard_concept_map_for_statement(statement: str) -> dict[str, str]:
    if statement == "cashflow":
        merged = dict(STANDARD_CONCEPT_TO_KEY)
        merged.update(CASHFLOW_STANDARD_CONCEPT_OVERRIDES)
        return merged
    return STANDARD_CONCEPT_TO_KEY


def canonical_key_from_standard(standard_concept: str | None, *, statement: str = "income") -> str | None:
    if not standard_concept:
        return None
    return standard_concept_map_for_statement(statement).get(str(standard_concept).strip())


def canonical_key_from_raw(concept: str | None) -> str | None:
    if not concept:
        return None
    tag = _strip_namespace(concept)
    return RAW_TAG_TO_KEY.get(tag)


def canonical_keys_for_statement(statement: str) -> tuple[str, ...]:
    from ingest.concept_map import STATEMENT_METRIC_ORDER

    return STATEMENT_METRIC_ORDER.get(statement, ())
