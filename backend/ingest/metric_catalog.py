"""Canonical SEC financial metrics — single source of truth for normalization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Applicability = Literal["always", "when_reported", "industry_optional"]
StatementKey = Literal["income", "balance", "cashflow"]


@dataclass(frozen=True)
class MetricAlias:
    namespace: str  # us-gaap | dei
    tag: str


@dataclass(frozen=True)
class MetricDef:
    key: str
    label: str
    statement: StatementKey
    aliases: tuple[MetricAlias, ...]
    unit: str = "USD"
    applicability: Applicability = "when_reported"
    comps_fields: tuple[str, ...] = ()


def _a(ns: str, tag: str) -> MetricAlias:
    return MetricAlias(namespace=ns, tag=tag)


METRICS: tuple[MetricDef, ...] = (
    # --- Income ---
    MetricDef(
        "revenue",
        "Revenue",
        "income",
        (
            _a("us-gaap", "Revenues"),
            _a("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
            _a("us-gaap", "SalesRevenueNet"),
            _a("us-gaap", "RevenueFromContractWithCustomerIncludingAssessedTax"),
        ),
        applicability="always",
        comps_fields=("revenue", "revenue_growth_yoy"),
    ),
    MetricDef(
        "cost_of_revenue",
        "Cost of Revenue",
        "income",
        (
            _a("us-gaap", "CostOfRevenue"),
            _a("us-gaap", "CostOfGoodsAndServicesSold"),
        ),
        applicability="industry_optional",
        comps_fields=("gross_margin",),
    ),
    MetricDef(
        "gross_profit",
        "Gross Profit",
        "income",
        (_a("us-gaap", "GrossProfit"),),
        applicability="industry_optional",
        comps_fields=("gross_margin",),
    ),
    MetricDef(
        "research_and_development",
        "Research & Development",
        "income",
        (_a("us-gaap", "ResearchAndDevelopmentExpense"),),
    ),
    MetricDef(
        "selling_general_admin",
        "SG&A",
        "income",
        (
            _a("us-gaap", "SellingGeneralAndAdministrativeExpense"),
            _a("us-gaap", "GeneralAndAdministrativeExpense"),
        ),
    ),
    MetricDef(
        "operating_income",
        "Operating Income",
        "income",
        (_a("us-gaap", "OperatingIncomeLoss"),),
        applicability="always",
        comps_fields=("operating_margin",),
    ),
    MetricDef(
        "interest_expense",
        "Interest Expense",
        "income",
        (
            _a("us-gaap", "InterestExpense"),
            _a("us-gaap", "InterestExpenseDebt"),
        ),
    ),
    MetricDef(
        "income_before_tax",
        "Income Before Tax",
        "income",
        (
            _a("us-gaap", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"),
            _a("us-gaap", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"),
        ),
    ),
    MetricDef(
        "income_tax_expense",
        "Income Tax Expense",
        "income",
        (
            _a("us-gaap", "IncomeTaxExpenseBenefit"),
            _a("us-gaap", "CurrentIncomeTaxExpenseBenefit"),
        ),
    ),
    MetricDef(
        "depreciation_and_amortization",
        "Depreciation & Amortization",
        "income",
        (
            _a("us-gaap", "DepreciationDepletionAndAmortization"),
            _a("us-gaap", "DepreciationAndAmortization"),
        ),
        comps_fields=("ebitda",),
    ),
    MetricDef(
        "depreciation",
        "Depreciation",
        "income",
        (_a("us-gaap", "Depreciation"),),
        comps_fields=("ebitda",),
    ),
    MetricDef(
        "amortization",
        "Amortization",
        "income",
        (
            _a("us-gaap", "AmortizationOfIntangibleAssets"),
            _a("us-gaap", "AmortizationOfFinancingCostsAndDiscounts"),
        ),
        comps_fields=("ebitda",),
    ),
    MetricDef(
        "net_income",
        "Net Income",
        "income",
        (
            _a("us-gaap", "NetIncomeLoss"),
            _a("us-gaap", "ProfitLoss"),
            _a("us-gaap", "NetIncomeLossAvailableToCommonStockholdersBasic"),
            _a("us-gaap", "NetIncomeLossAvailableToCommonStockholdersDiluted"),
        ),
        applicability="always",
        comps_fields=("net_income", "net_margin", "roe", "roa", "net_income_growth_yoy"),
    ),
    MetricDef(
        "eps_basic",
        "EPS (Basic)",
        "income",
        (_a("us-gaap", "EarningsPerShareBasic"),),
        unit="USD/shares",
    ),
    MetricDef(
        "eps_diluted",
        "EPS (Diluted)",
        "income",
        (_a("us-gaap", "EarningsPerShareDiluted"),),
        unit="USD/shares",
        comps_fields=("eps_diluted",),
    ),
    MetricDef(
        "weighted_avg_shares_basic",
        "Weighted Avg Shares (Basic)",
        "income",
        (
            _a("us-gaap", "WeightedAverageNumberOfShareOutstandingBasic"),
            _a("us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic"),
        ),
        unit="shares",
    ),
    MetricDef(
        "weighted_avg_shares_diluted",
        "Weighted Avg Shares (Diluted)",
        "income",
        (_a("us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding"),),
        unit="shares",
        comps_fields=("shares_outstanding", "book_value_per_share"),
    ),
    MetricDef(
        "ebitda",
        "EBITDA",
        "income",
        (),
        applicability="when_reported",
        comps_fields=("ebitda",),
    ),
    # --- Balance ---
    MetricDef(
        "cash",
        "Cash & Equivalents",
        "balance",
        (
            _a("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
            _a("us-gaap", "CashCashEquivalentsAndShortTermInvestments"),
        ),
        comps_fields=("net_debt",),
    ),
    MetricDef(
        "short_term_investments",
        "Short-Term Investments",
        "balance",
        (
            _a("us-gaap", "ShortTermInvestments"),
            _a("us-gaap", "MarketableSecuritiesCurrent"),
        ),
    ),
    MetricDef(
        "total_assets",
        "Total Assets",
        "balance",
        (_a("us-gaap", "Assets"),),
        applicability="always",
        comps_fields=("total_assets", "roa"),
    ),
    MetricDef(
        "total_liabilities",
        "Total Liabilities",
        "balance",
        (_a("us-gaap", "Liabilities"),),
    ),
    MetricDef(
        "stockholders_equity",
        "Stockholders' Equity",
        "balance",
        (
            _a("us-gaap", "StockholdersEquity"),
            _a("us-gaap", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
        ),
        applicability="always",
        comps_fields=("stockholders_equity", "roe", "debt_to_equity", "book_value_per_share"),
    ),
    MetricDef(
        "long_term_debt",
        "Long-Term Debt",
        "balance",
        (
            _a("us-gaap", "LongTermDebt"),
            _a("us-gaap", "LongTermDebtNoncurrent"),
        ),
        comps_fields=("net_debt", "debt_to_equity"),
    ),
    MetricDef(
        "short_term_debt",
        "Short-Term Debt",
        "balance",
        (
            _a("us-gaap", "ShortTermBorrowings"),
            _a("us-gaap", "DebtCurrent"),
            _a("us-gaap", "LongTermDebtCurrent"),
        ),
        comps_fields=("net_debt", "debt_to_equity"),
    ),
    MetricDef(
        "total_debt",
        "Total Debt",
        "balance",
        (
            _a("us-gaap", "Debt"),
            _a("us-gaap", "LiabilitiesOtherThanLongtermDebtNoncurrent"),
        ),
        comps_fields=("net_debt", "debt_to_equity"),
    ),
    MetricDef(
        "shares_outstanding",
        "Shares Outstanding",
        "balance",
        (
            _a("us-gaap", "CommonStockSharesOutstanding"),
            _a("dei", "EntityCommonStockSharesOutstanding"),
        ),
        unit="shares",
        comps_fields=("shares_outstanding", "book_value_per_share"),
    ),
    # --- Cash flow ---
    MetricDef(
        "operating_cash_flow",
        "Operating Cash Flow",
        "cashflow",
        (_a("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),),
        applicability="always",
        comps_fields=("operating_cash_flow", "free_cash_flow", "fcf_margin"),
    ),
    MetricDef(
        "capex",
        "Capital Expenditures",
        "cashflow",
        (
            _a("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"),
            _a("us-gaap", "PaymentsToAcquireProductiveAssets"),
            _a("us-gaap", "PaymentsToAcquirePropertyAndEquipment"),
        ),
        comps_fields=("capex", "free_cash_flow", "fcf_margin"),
    ),
    MetricDef(
        "free_cash_flow",
        "Free Cash Flow",
        "cashflow",
        (),
        applicability="when_reported",
        comps_fields=("free_cash_flow", "fcf_margin"),
    ),
)

METRICS_BY_KEY: dict[str, MetricDef] = {m.key: m for m in METRICS}

INCOME_METRIC_ORDER: tuple[str, ...] = (
    "revenue",
    "cost_of_revenue",
    "gross_profit",
    "research_and_development",
    "selling_general_admin",
    "operating_income",
    "depreciation_and_amortization",
    "depreciation",
    "amortization",
    "ebitda",
    "interest_expense",
    "income_before_tax",
    "income_tax_expense",
    "net_income",
    "eps_basic",
    "eps_diluted",
    "weighted_avg_shares_basic",
    "weighted_avg_shares_diluted",
)

BALANCE_METRIC_ORDER: tuple[str, ...] = (
    "cash",
    "short_term_investments",
    "total_assets",
    "total_liabilities",
    "stockholders_equity",
    "short_term_debt",
    "long_term_debt",
    "total_debt",
    "shares_outstanding",
)

CASHFLOW_METRIC_ORDER: tuple[str, ...] = (
    "depreciation_and_amortization",
    "operating_cash_flow",
    "capex",
    "free_cash_flow",
)

STATEMENT_METRIC_ORDER: dict[str, tuple[str, ...]] = {
    "income": INCOME_METRIC_ORDER,
    "balance": BALANCE_METRIC_ORDER,
    "cashflow": CASHFLOW_METRIC_ORDER,
}


def metrics_for_statement(statement: StatementKey) -> tuple[MetricDef, ...]:
    base = tuple(m for m in METRICS if m.statement == statement)
    if statement == "cashflow":
        da = METRICS_BY_KEY.get("depreciation_and_amortization")
        if da is not None and da not in base:
            return base + (da,)
    return base


def line_labels() -> dict[str, str]:
    return {m.key: m.label for m in METRICS}


def statement_concepts_legacy() -> dict[str, dict[str, list[str]]]:
    """Backward-compatible tag-only map (us-gaap tags only)."""
    out: dict[str, dict[str, list[str]]] = {
        "income": {},
        "balance": {},
        "cashflow": {},
    }
    for m in METRICS:
        tags = [a.tag for a in m.aliases if a.namespace == "us-gaap"]
        if tags:
            out[m.statement][m.key] = tags
    return out
