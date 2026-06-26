"""Curated detailed-analysis metrics from edgartools statement DataFrames."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd

from ingest.fiscal_calendar import fiscal_year_from_period_end
from ingest.statement_extract import (
    _num,
    _pick_raw_tag,
    _pick_standard_concept,
    period_columns,
    period_end_from_col,
    smart_revenue,
    strip_tag,
)

SourceKind = Literal["xbrl", "derived", "n/a"]

DETAILED_INCOME_ORDER: tuple[str, ...] = (
    "revenue",
    "cost_of_revenue",
    "gross_profit",
    "operating_cost",
    "operating_income",
    "ebitda",
    "depreciation",
    "amortization",
    "interest_expense",
    "income_tax_expense",
    "net_income",
)

DETAILED_BALANCE_ORDER: tuple[str, ...] = (
    "current_assets",
    "non_current_assets",
    "total_assets",
    "current_liabilities",
    "non_current_liabilities",
    "total_liabilities",
    "stockholders_equity",
    "cash_end_of_period",
)

DETAILED_CASHFLOW_ORDER: tuple[str, ...] = (
    "operating_cash_flow",
    "investing_cash_flow",
    "free_cash_flow",
    "financing_cash_flow",
    "net_cash_change",
)

DETAILED_STATEMENT_ORDER: dict[str, tuple[str, ...]] = {
    "income": DETAILED_INCOME_ORDER,
    "balance": DETAILED_BALANCE_ORDER,
    "cashflow": DETAILED_CASHFLOW_ORDER,
}

METRIC_STATEMENT: dict[str, str] = {
    **{k: "income" for k in DETAILED_INCOME_ORDER},
    **{k: "balance" for k in DETAILED_BALANCE_ORDER},
    **{k: "cashflow" for k in DETAILED_CASHFLOW_ORDER},
}

DETAILED_LABELS: dict[str, str] = {
    "revenue": "Revenue",
    "cost_of_revenue": "COGS",
    "gross_profit": "Gross Profit",
    "operating_cost": "Operating Cost",
    "operating_income": "Operating Income / EBIT",
    "ebitda": "EBITDA",
    "depreciation": "Depreciation",
    "amortization": "Amortization",
    "interest_expense": "Interest",
    "income_tax_expense": "Tax",
    "net_income": "Net Income",
    "current_assets": "Current Assets",
    "non_current_assets": "Non-Current Assets",
    "current_liabilities": "Current Liabilities",
    "non_current_liabilities": "Non-Current Liabilities",
    "total_assets": "Total Assets",
    "total_liabilities": "Total Liabilities",
    "stockholders_equity": "Stockholders' Equity",
    "cash_end_of_period": "Cash at Period End",
    "operating_cash_flow": "CFOA",
    "investing_cash_flow": "CFIO (Investing)",
    "free_cash_flow": "Free Cash Flow",
    "financing_cash_flow": "CFFO (Financing)",
    "net_cash_change": "Net Change in Cash (FY)",
}

BALANCE_GROUP_LABELS: dict[str, str] = {
    "current_assets": "Assets",
    "non_current_assets": "Assets",
    "total_assets": "Totals",
    "current_liabilities": "Liabilities",
    "non_current_liabilities": "Liabilities",
    "total_liabilities": "Totals",
    "stockholders_equity": "Equity",
    "cash_end_of_period": "Cash",
}

TOTAL_OPERATING_LABEL_RE = re.compile(
    r"total\s+(noninterest\s+)?operating\s+expense|total\s+operating\s+expense",
    re.IGNORECASE,
)
TOTAL_COSTS_BLOCK_RE = re.compile(
    r"total\s+costs?\s+and\s+expenses",
    re.IGNORECASE,
)

KNOWN_BANK_TICKERS = frozenset({
    "AXP",
    "BAC",
    "BK",
    "C",
    "GS",
    "JPM",
    "MS",
    "PNC",
    "SCHW",
    "STT",
    "TFC",
    "USB",
    "WFC",
})


@dataclass
class MetricCell:
    key: str
    value: float | None = None
    xbrl_tag: str | None = None
    label: str | None = None
    source_statement: str | None = None
    source: SourceKind = "xbrl"
    warning: str | None = None

    def to_line_item(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "key": self.key,
            "label": DETAILED_LABELS.get(self.key, self.key),
            "value": self.value,
            "unit": "USD",
            "source": self.source if self.source != "n/a" else "xbrl",
            "xbrl_tag": self.xbrl_tag,
        }
        if self.source == "derived":
            out["source"] = "derived"
            out["derived_from"] = self._derived_from()
        if self.warning:
            out["warning"] = self.warning
        return out

    def _derived_from(self) -> list[str] | None:
        if self.key == "free_cash_flow":
            return ["operating_cash_flow", "capex"]
        if self.key == "operating_cost" and self.xbrl_tag == "sum_rd_sga":
            return ["research_and_development", "selling_general_admin"]
        if self.key == "operating_cost" and self.xbrl_tag == "derived_gp_minus_oi":
            return ["gross_profit", "operating_income"]
        if self.key == "gross_profit" and self.source == "derived":
            return ["revenue", "cost_of_revenue"]
        if self.key == "ebitda":
            return ["operating_income", "depreciation", "amortization"]
        if self.key in ("non_current_assets", "non_current_liabilities"):
            if self.key == "non_current_assets":
                return ["total_assets", "current_assets"]
            return ["total_liabilities", "current_liabilities"]
        return None


@dataclass
class DetailedPeriod:
    fiscal_year: int
    fiscal_period: str
    period_end: str
    income: dict[str, MetricCell] = field(default_factory=dict)
    balance: dict[str, MetricCell] = field(default_factory=dict)
    cashflow: dict[str, MetricCell] = field(default_factory=dict)
    is_bank_style: bool = False
    accounting_equation_ok: bool | None = None


@dataclass
class DetailedAnalysisSnapshot:
    ticker: str
    entity_name: str
    cik: str
    fetched_at: str
    source: str
    periods: list[DetailedPeriod] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    integrity_checks: list[str] = field(default_factory=list)
    is_bank_style: bool = False


def _row_label(df: pd.DataFrame, period_col: str, tag: str | None) -> str | None:
    if not tag or df is None:
        return None
    for _, row in df.iterrows():
        if strip_tag(row.get("concept")) == tag:
            return str(row.get("label") or "") or None
    return None


def _make_cell(
    key: str,
    value: float | None,
    *,
    xbrl_tag: str | None = None,
    label: str | None = None,
    source_statement: str | None = None,
    source: SourceKind = "xbrl",
    warning: str | None = None,
) -> MetricCell:
    return MetricCell(
        key=key,
        value=value,
        xbrl_tag=xbrl_tag,
        label=label,
        source_statement=source_statement,
        source=source,
        warning=warning,
    )


def _na_cell(key: str, *, warning: str | None = "not_applicable") -> MetricCell:
    return _make_cell(key, None, source="n/a", warning=warning)


def _is_breakdown_row(row: pd.Series) -> bool:
    dim = row.get("dimension")
    if dim is None or (isinstance(dim, float) and pd.isna(dim)):
        return False
    if dim in (0, "0", False):
        return False
    return True


def _pick_cost_of_revenue(df: pd.DataFrame, period_col: str) -> tuple[float | None, str | None]:
    _, rev_tag = smart_revenue(df, period_col)
    if rev_tag == "RevenuesNetOfInterestExpense":
        return None, None

    val, tag = _pick_raw_tag(
        df, period_col, "CostOfRevenue", label_needles=("total", "cost of revenue")
    )
    if val is not None:
        return val, tag

    cogs_rows: list[tuple[float, str, str]] = []
    for _, row in df.iterrows():
        if strip_tag(row.get("concept")) != "CostOfGoodsAndServicesSold":
            continue
        if _is_breakdown_row(row):
            continue
        val = _num(row.get(period_col))
        if val is not None:
            cogs_rows.append(
                (val, strip_tag(row.get("concept")), str(row.get("label") or ""))
            )

    if len(cogs_rows) == 1:
        single_val, single_tag, _ = cogs_rows[0]
    else:
        single_val, single_tag = None, None

    automotive_cogs: float | None = None
    automotive_tag: str | None = None
    for val, tag, label in cogs_rows:
        lower = label.lower()
        if "automotive" in lower or "cost of sales" in lower or "merchandise" in lower:
            automotive_cogs = val
            automotive_tag = tag
            break
    if automotive_cogs is None and cogs_rows:
        automotive_cogs, automotive_tag, _ = cogs_rows[0]

    financial_cost: float | None = None
    for _, row in df.iterrows():
        if strip_tag(row.get("concept")) != "OperatingCostsAndExpenses":
            continue
        label = str(row.get("label") or "").lower()
        if "financial" not in label and "gm financial" not in label:
            continue
        val = _num(row.get(period_col))
        if val is not None:
            financial_cost = val
            break

    if automotive_cogs is not None and financial_cost is not None:
        return automotive_cogs + financial_cost, "conglomerate_cogs_sum"

    if single_val is not None:
        return single_val, single_tag

    if cogs_rows:
        val, tag, _ = max(cogs_rows, key=lambda x: abs(x[0]))
        return val, tag

    val, tag = _pick_standard_concept(df, period_col, "CostOfGoodsAndServicesSold")
    if val is not None:
        return val, tag
    return _pick_raw_tag(df, period_col, "CostOfGoodsAndServicesSold")


def _pick_gross_profit(df: pd.DataFrame, period_col: str) -> tuple[float | None, str | None]:
    val, tag = _pick_raw_tag(df, period_col, "GrossProfit")
    if val is not None:
        return val, tag
    return _pick_standard_concept(df, period_col, "GrossProfit")


def _pick_operating_cost(df: pd.DataFrame, period_col: str) -> MetricCell:
    for _, row in df.iterrows():
        if strip_tag(row.get("concept")) != "OperatingExpenses":
            continue
        label = str(row.get("label") or "")
        if TOTAL_COSTS_BLOCK_RE.search(label):
            continue
        if TOTAL_OPERATING_LABEL_RE.search(label):
            val = _num(row.get(period_col))
            if val is not None:
                return _make_cell(
                    "operating_cost",
                    val,
                    xbrl_tag="OperatingExpenses",
                    label=label,
                    source_statement="income",
                )

    val, tag = _pick_standard_concept(
        df,
        period_col,
        "TotalOperatingExpenses",
        label_needles=("total operating", "operating expense"),
    )
    if val is not None:
        label = _row_label(df, period_col, tag) or ""
        if not TOTAL_COSTS_BLOCK_RE.search(label):
            return _make_cell(
                "operating_cost",
                val,
                xbrl_tag=tag,
                label=label or None,
                source_statement="income",
            )

    rd, _ = _pick_standard_concept(
        df, period_col, "ResearchAndDevelopmentExpenses"
    )
    sga, _ = _pick_standard_concept(
        df, period_col, "SellingGeneralAndAdminExpenses"
    )
    if rd is not None and sga is not None:
        return _make_cell(
            "operating_cost",
            rd + sga,
            xbrl_tag="sum_rd_sga",
            label="R&D + SG&A",
            source_statement="income",
            source="derived",
            warning="summed_rd_sga",
        )
    if sga is not None:
        return _make_cell(
            "operating_cost",
            sga,
            xbrl_tag="SellingGeneralAndAdminExpenses",
            label=_row_label(df, period_col, "SellingGeneralAndAdminExpenses"),
            source_statement="income",
        )

    val, tag = _pick_raw_tag(df, period_col, "NoninterestExpense")
    if val is None:
        val, tag = _pick_standard_concept(df, period_col, "NonInterestExpense")
    if val is not None:
        return _make_cell(
            "operating_cost",
            val,
            xbrl_tag=tag,
            label=_row_label(df, period_col, tag),
            source_statement="income",
            warning="bank_noninterest_expense",
        )

    return _make_cell("operating_cost", None, source_statement="income")


def _is_bank_style(income_df: pd.DataFrame, period_col: str) -> bool:
    val, tag = smart_revenue(income_df, period_col)
    if val is not None and tag == "RevenuesNetOfInterestExpense":
        return True
    cogs, _ = _pick_cost_of_revenue(income_df, period_col)
    gp, _ = _pick_gross_profit(income_df, period_col)
    if cogs is not None or gp is not None:
        return False
    return val is not None


def _pick_depreciation(
    income_df: pd.DataFrame,
    cashflow_df: pd.DataFrame | None,
    period_col: str,
) -> MetricCell:
    for tag in (
        "Depreciation",
        "DepreciationAndAmortization",
        "DepreciationDepletionAndAmortization",
    ):
        val, picked = _pick_raw_tag(income_df, period_col, tag)
        if val is not None:
            return _make_cell(
                "depreciation",
                val,
                xbrl_tag=picked,
                label=_row_label(income_df, period_col, picked),
                source_statement="income",
            )

    val, tag = _pick_standard_concept(income_df, period_col, "DepreciationExpense")
    if val is not None:
        return _make_cell(
            "depreciation",
            val,
            xbrl_tag=tag,
            label=_row_label(income_df, period_col, tag),
            source_statement="income",
        )

    if cashflow_df is not None:
        val, tag = _pick_raw_tag(
            cashflow_df, period_col, "DepreciationDepletionAndAmortization"
        )
        if val is None:
            val, tag = _pick_standard_concept(
                cashflow_df, period_col, "DepreciationExpense"
            )
        if val is not None:
            return _make_cell(
                "depreciation",
                val,
                xbrl_tag=tag,
                label=_row_label(cashflow_df, period_col, tag),
                source_statement="cashflow",
                warning="combined_da_from_cashflow",
            )

        da_sum, da_tag = _pick_cf_depreciation_sum(cashflow_df, period_col)
        if da_sum is not None:
            return _make_cell(
                "depreciation",
                da_sum,
                xbrl_tag=da_tag,
                label="Sum of cash flow D&A add-backs",
                source_statement="cashflow",
                source="derived",
                warning="summed_cf_depreciation_lines",
            )

    return _make_cell("depreciation", None, source_statement="income")


def _pick_cf_depreciation_sum(
    cashflow_df: pd.DataFrame, period_col: str
) -> tuple[float | None, str | None]:
    """Sum filer-specific D&A add-back lines when standard tags are absent (e.g. GM)."""
    total = 0.0
    seen_labels: set[str] = set()
    for _, row in cashflow_df.iterrows():
        if _is_breakdown_row(row):
            continue
        concept = strip_tag(row.get("concept")) or ""
        label = str(row.get("label") or "")
        lower_label = label.lower()
        if "depreciation" not in concept.lower() and "depreciation" not in lower_label:
            continue
        if lower_label in seen_labels:
            continue
        val = _num(row.get(period_col))
        if val is None:
            continue
        seen_labels.add(lower_label)
        total += abs(val)
    if total > 0:
        return total, "cf_depreciation_sum"
    return None, None


def _pick_amortization(income_df: pd.DataFrame, period_col: str) -> MetricCell:
    val, tag = _pick_raw_tag(income_df, period_col, "AmortizationOfIntangibleAssets")
    if val is None:
        val, tag = _pick_standard_concept(
            income_df, period_col, "AmortizationOfIntangibles"
        )
    if val is not None:
        return _make_cell(
            "amortization",
            val,
            xbrl_tag=tag,
            label=_row_label(income_df, period_col, tag),
            source_statement="income",
        )
    return _make_cell("amortization", None, source_statement="income")


def _pick_interest(
    income_df: pd.DataFrame,
    cashflow_df: pd.DataFrame | None,
    period_col: str,
) -> MetricCell:
    val, tag = _pick_raw_tag(income_df, period_col, "InterestExpense")
    if val is None:
        val, tag = _pick_standard_concept(income_df, period_col, "InterestExpense")
    if val is not None:
        return _make_cell(
            "interest_expense",
            val,
            xbrl_tag=tag,
            label=_row_label(income_df, period_col, tag),
            source_statement="income",
        )

    if cashflow_df is not None:
        val, tag = _pick_raw_tag(cashflow_df, period_col, "InterestPaidNet")
        if val is not None:
            return _make_cell(
                "interest_expense",
                val,
                xbrl_tag=tag,
                label=_row_label(cashflow_df, period_col, tag),
                source_statement="cashflow",
                warning="interest_from_cashflow",
            )

    return _make_cell("interest_expense", None, source_statement="income")


def _pick_balance_total(
    df: pd.DataFrame,
    period_col: str,
    key: str,
    *,
    raw_tag: str,
    standard_concept: str,
    label_needles: tuple[str, ...],
) -> MetricCell:
    val, tag = _pick_raw_tag(df, period_col, raw_tag, label_needles=label_needles)
    if val is not None:
        return _make_cell(
            key,
            val,
            xbrl_tag=tag,
            label=_row_label(df, period_col, tag),
            source_statement="balance",
        )
    val, tag = _pick_standard_concept(
        df, period_col, standard_concept, label_needles=label_needles
    )
    if val is not None:
        return _make_cell(
            key,
            val,
            xbrl_tag=tag,
            label=_row_label(df, period_col, tag),
            source_statement="balance",
        )
    return _make_cell(key, None, source_statement="balance")


def _pick_equity(df: pd.DataFrame, period_col: str) -> MetricCell:
    for sc, needles in (
        ("AllEquityBalance", ("total stockholders", "total shareholders", "total equity")),
        ("CommonEquity", ("total stockholders", "total shareholders", "total equity")),
    ):
        val, tag = _pick_standard_concept(df, period_col, sc, label_needles=needles)
        if val is not None:
            return _make_cell(
                "stockholders_equity",
                val,
                xbrl_tag=tag,
                label=_row_label(df, period_col, tag),
                source_statement="balance",
            )
    val, tag = _pick_raw_tag(
        df,
        period_col,
        "StockholdersEquity",
        label_needles=("total", "stockholders", "shareholders"),
    )
    if val is not None:
        return _make_cell(
            "stockholders_equity",
            val,
            xbrl_tag=tag,
            label=_row_label(df, period_col, tag),
            source_statement="balance",
        )
    return _make_cell("stockholders_equity", None, source_statement="balance")


def _pick_cashflow_section_total(
    df: pd.DataFrame,
    period_col: str,
    key: str,
    raw_tag: str,
    label_needles: tuple[str, ...],
) -> MetricCell:
    val, tag = _pick_raw_tag(df, period_col, raw_tag, label_needles=label_needles)
    if val is not None:
        return _make_cell(
            key,
            val,
            xbrl_tag=tag,
            label=_row_label(df, period_col, tag),
            source_statement="cashflow",
        )
    return _make_cell(key, None, source_statement="cashflow")


def _pick_operating_cash_flow(df: pd.DataFrame, period_col: str) -> MetricCell:
    val, tag = _pick_raw_tag(
        df,
        period_col,
        "NetCashProvidedByUsedInOperatingActivities",
        label_needles=(
            "net cash",
            "cash generated",
            "cash provided",
            "operating activities",
        ),
    )
    if val is not None:
        return _make_cell(
            "operating_cash_flow",
            val,
            xbrl_tag=tag,
            label=_row_label(df, period_col, tag),
            source_statement="cashflow",
        )
    val, tag = _pick_standard_concept(
        df,
        period_col,
        "NetCashFromOperatingActivities",
        label_needles=(
            "net cash",
            "cash generated",
            "cash provided",
            "operating activities",
        ),
    )
    if val is not None:
        return _make_cell(
            "operating_cash_flow",
            val,
            xbrl_tag=tag,
            label=_row_label(df, period_col, tag),
            source_statement="cashflow",
        )
    return _make_cell("operating_cash_flow", None, source_statement="cashflow")


def _pick_investing_cash_flow(df: pd.DataFrame, period_col: str) -> MetricCell:
    return _pick_cashflow_section_total(
        df,
        period_col,
        "investing_cash_flow",
        "NetCashProvidedByUsedInInvestingActivities",
        ("investing activities", "net cash"),
    )


def _pick_financing_cash_flow(df: pd.DataFrame, period_col: str) -> MetricCell:
    return _pick_cashflow_section_total(
        df,
        period_col,
        "financing_cash_flow",
        "NetCashProvidedByUsedInFinancingActivities",
        ("financing activities", "net cash"),
    )


def _pick_net_cash_change(df: pd.DataFrame, period_col: str) -> MetricCell:
    for tag in (
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
        "CashAndCashEquivalentsPeriodIncreaseDecrease",
    ):
        val, picked = _pick_raw_tag(
            df,
            period_col,
            tag,
            label_needles=("increase", "decrease", "change", "cash"),
        )
        if val is not None:
            return _make_cell(
                "net_cash_change",
                val,
                xbrl_tag=picked,
                label=_row_label(df, period_col, picked),
                source_statement="cashflow",
            )
    val, tag = _pick_standard_concept(df, period_col, "NetChangeInCash")
    if val is not None:
        return _make_cell(
            "net_cash_change",
            val,
            xbrl_tag=tag,
            label=_row_label(df, period_col, tag),
            source_statement="cashflow",
        )
    return _make_cell("net_cash_change", None, source_statement="cashflow")


def _pick_capex(df: pd.DataFrame, period_col: str) -> float | None:
    val, _ = _pick_standard_concept(
        df,
        period_col,
        "CapitalExpenses",
        label_needles=("capital", "property", "equipment"),
    )
    if val is not None:
        return val
    val, _ = _pick_raw_tag(
        df, period_col, "PaymentsToAcquirePropertyPlantAndEquipment"
    )
    return val


def _pick_total_assets(df: pd.DataFrame, period_col: str) -> MetricCell:
    val, tag = _pick_raw_tag(df, period_col, "Assets", label_needles=("total assets",))
    if val is None:
        val, tag = _pick_standard_concept(
            df, period_col, "Assets", label_needles=("total assets",), prefer_largest=True
        )
    if val is not None:
        return _make_cell(
            "total_assets",
            val,
            xbrl_tag=tag,
            label=_row_label(df, period_col, tag),
            source_statement="balance",
        )
    return _make_cell("total_assets", None, source_statement="balance")


def _pick_total_liabilities(df: pd.DataFrame, period_col: str) -> MetricCell:
    val, tag = _pick_raw_tag(
        df, period_col, "Liabilities", label_needles=("total liabilities",)
    )
    if val is None:
        val, tag = _pick_standard_concept(
            df,
            period_col,
            "Liabilities",
            label_needles=("total liabilities",),
            prefer_largest=True,
        )
    if val is not None:
        return _make_cell(
            "total_liabilities",
            val,
            xbrl_tag=tag,
            label=_row_label(df, period_col, tag),
            source_statement="balance",
        )
    return _make_cell("total_liabilities", None, source_statement="balance")


def _pick_cash_end_of_period(df: pd.DataFrame, period_col: str) -> MetricCell:
    for tag in ("CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsAndShortTermInvestments"):
        val, picked = _pick_raw_tag(df, period_col, tag)
        if val is not None:
            return _make_cell(
                "cash_end_of_period",
                val,
                xbrl_tag=picked,
                label=_row_label(df, period_col, picked),
                source_statement="balance",
            )
    val, tag = _pick_standard_concept(df, period_col, "CashAndMarketableSecurities")
    if val is not None:
        return _make_cell(
            "cash_end_of_period",
            val,
            xbrl_tag=tag,
            label=_row_label(df, period_col, tag),
            source_statement="balance",
        )
    return _make_cell("cash_end_of_period", None, source_statement="balance")


def _da_addback_for_ebitda(inc: dict[str, MetricCell]) -> tuple[float, list[str]] | None:
    depr = inc.get("depreciation")
    amort = inc.get("amortization")
    if depr and depr.value is not None and amort and amort.value is not None:
        return abs(depr.value) + abs(amort.value), ["depreciation", "amortization"]
    if depr and depr.value is not None:
        return abs(depr.value), ["depreciation"]
    return None


def apply_detailed_derivations(period: DetailedPeriod) -> None:
    """Fill gaps with safe derived metrics when filed XBRL lines are missing."""
    inc = period.income

    gp = inc.get("gross_profit")
    if gp and gp.value is None and gp.source != "n/a":
        rev = inc.get("revenue")
        cogs = inc.get("cost_of_revenue")
        if (
            rev
            and cogs
            and rev.value is not None
            and cogs.value is not None
        ):
            inc["gross_profit"] = _make_cell(
                "gross_profit",
                rev.value - abs(cogs.value),
                xbrl_tag="derived_gross_profit",
                label="Revenue − COGS",
                source_statement="income",
                source="derived",
            )

    oc = inc.get("operating_cost")
    if oc and oc.value is None:
        gp2 = inc.get("gross_profit")
        oi = inc.get("operating_income")
        if (
            gp2
            and oi
            and gp2.value is not None
            and oi.value is not None
        ):
            inc["operating_cost"] = _make_cell(
                "operating_cost",
                gp2.value - oi.value,
                xbrl_tag="derived_gp_minus_oi",
                label="Gross profit − Operating income",
                source_statement="income",
                source="derived",
                warning="derived_gp_minus_oi",
            )

    oi = inc.get("operating_income")
    da = _da_addback_for_ebitda(inc)
    if oi and oi.value is not None and da is not None:
        addback, da_keys = da
        inc["ebitda"] = _make_cell(
            "ebitda",
            oi.value + addback,
            xbrl_tag="derived_ebitda",
            label="Operating income + D&A",
            source_statement="income",
            source="derived",
            warning=f"derived_from_{'_'.join(da_keys)}",
        )

    bal = period.balance
    ta = bal.get("total_assets")
    ca = bal.get("current_assets")
    nca = bal.get("non_current_assets")
    if (
        nca
        and nca.value is None
        and ta
        and ca
        and ta.value is not None
        and ca.value is not None
    ):
        bal["non_current_assets"] = _make_cell(
            "non_current_assets",
            ta.value - ca.value,
            xbrl_tag="derived_non_current_assets",
            label="Total assets − Current assets",
            source_statement="balance",
            source="derived",
            warning="derived_from_balance_arithmetic",
        )

    tl = bal.get("total_liabilities")
    cl = bal.get("current_liabilities")
    ncl = bal.get("non_current_liabilities")
    if (
        ncl
        and ncl.value is None
        and tl
        and cl
        and tl.value is not None
        and cl.value is not None
    ):
        bal["non_current_liabilities"] = _make_cell(
            "non_current_liabilities",
            tl.value - cl.value,
            xbrl_tag="derived_non_current_liabilities",
            label="Total liabilities − Current liabilities",
            source_statement="balance",
            source="derived",
            warning="derived_from_balance_arithmetic",
        )

    _update_accounting_equation_flag(period)


def _update_accounting_equation_flag(period: DetailedPeriod) -> None:
    bal = period.balance
    ta = bal.get("total_assets")
    tl = bal.get("total_liabilities")
    eq = bal.get("stockholders_equity")
    if not ta or not tl or not eq:
        period.accounting_equation_ok = None
        return
    if ta.value is None or tl.value is None or eq.value is None:
        period.accounting_equation_ok = None
        return
    lhs = ta.value
    rhs = tl.value + eq.value
    period.accounting_equation_ok = _relative_diff(lhs, rhs) <= 0.02


def extract_detailed_period(
    income_df: pd.DataFrame | None,
    balance_df: pd.DataFrame | None,
    cashflow_df: pd.DataFrame | None,
    period_col: str,
    *,
    fy_end_mmdd: str | None = None,
) -> DetailedPeriod:
    period_end = period_end_from_col(period_col)
    fy = fiscal_year_from_period_end(period_end, fy_end_mmdd=fy_end_mmdd) or 0

    income: dict[str, MetricCell] = {}
    balance: dict[str, MetricCell] = {}
    cashflow: dict[str, MetricCell] = {}
    bank = False

    if income_df is not None and period_col in income_df.columns:
        bank = _is_bank_style(income_df, period_col)

        val, tag = smart_revenue(income_df, period_col)
        income["revenue"] = _make_cell(
            "revenue",
            val,
            xbrl_tag=tag,
            label=_row_label(income_df, period_col, tag),
            source_statement="income",
        )

        if bank:
            income["cost_of_revenue"] = _na_cell("cost_of_revenue")
            income["gross_profit"] = _na_cell("gross_profit")
        else:
            val, tag = _pick_cost_of_revenue(income_df, period_col)
            income["cost_of_revenue"] = _make_cell(
                "cost_of_revenue",
                val,
                xbrl_tag=tag,
                label=_row_label(income_df, period_col, tag),
                source_statement="income",
            )
            val, tag = _pick_gross_profit(income_df, period_col)
            income["gross_profit"] = _make_cell(
                "gross_profit",
                val,
                xbrl_tag=tag,
                label=_row_label(income_df, period_col, tag),
                source_statement="income",
            )

        income["operating_cost"] = _pick_operating_cost(income_df, period_col)

        val, tag = _pick_raw_tag(income_df, period_col, "OperatingIncomeLoss")
        if val is None:
            val, tag = _pick_standard_concept(
                income_df, period_col, "OperatingIncomeLoss"
            )
        income["operating_income"] = _make_cell(
            "operating_income",
            val,
            xbrl_tag=tag,
            label=_row_label(income_df, period_col, tag),
            source_statement="income",
        )

        income["depreciation"] = _pick_depreciation(
            income_df, cashflow_df, period_col
        )
        income["amortization"] = _pick_amortization(income_df, period_col)
        income["interest_expense"] = _pick_interest(
            income_df, cashflow_df, period_col
        )

        val, tag = _pick_raw_tag(income_df, period_col, "IncomeTaxExpenseBenefit")
        if val is None:
            val, tag = _pick_standard_concept(income_df, period_col, "IncomeTaxes")
        income["income_tax_expense"] = _make_cell(
            "income_tax_expense",
            val,
            xbrl_tag=tag,
            label=_row_label(income_df, period_col, tag),
            source_statement="income",
        )

        val, tag = _pick_raw_tag(income_df, period_col, "NetIncomeLoss")
        if val is None:
            val, tag = _pick_standard_concept(income_df, period_col, "NetIncome")
        income["net_income"] = _make_cell(
            "net_income",
            val,
            xbrl_tag=tag,
            label=_row_label(income_df, period_col, tag),
            source_statement="income",
        )

    if balance_df is not None and period_col in balance_df.columns:
        balance["current_assets"] = _pick_balance_total(
            balance_df,
            period_col,
            "current_assets",
            raw_tag="AssetsCurrent",
            standard_concept="CurrentAssetsTotal",
            label_needles=("total current assets", "current assets"),
        )
        balance["non_current_assets"] = _pick_balance_total(
            balance_df,
            period_col,
            "non_current_assets",
            raw_tag="AssetsNoncurrent",
            standard_concept="NonCurrentAssetsTotal",
            label_needles=("total non-current assets", "non-current assets", "noncurrent"),
        )
        balance["current_liabilities"] = _pick_balance_total(
            balance_df,
            period_col,
            "current_liabilities",
            raw_tag="LiabilitiesCurrent",
            standard_concept="CurrentLiabilitiesTotal",
            label_needles=("total current liabilities", "current liabilities"),
        )
        balance["non_current_liabilities"] = _pick_balance_total(
            balance_df,
            period_col,
            "non_current_liabilities",
            raw_tag="LiabilitiesNoncurrent",
            standard_concept="NonCurrentLiabilitiesTotal",
            label_needles=(
                "total non-current liabilities",
                "non-current liabilities",
                "noncurrent",
            ),
        )
        balance["stockholders_equity"] = _pick_equity(balance_df, period_col)
        balance["total_assets"] = _pick_total_assets(balance_df, period_col)
        balance["total_liabilities"] = _pick_total_liabilities(balance_df, period_col)
        balance["cash_end_of_period"] = _pick_cash_end_of_period(balance_df, period_col)

    if cashflow_df is not None and period_col in cashflow_df.columns:
        cashflow["operating_cash_flow"] = _pick_operating_cash_flow(
            cashflow_df, period_col
        )
        cashflow["investing_cash_flow"] = _pick_investing_cash_flow(
            cashflow_df, period_col
        )
        cashflow["financing_cash_flow"] = _pick_financing_cash_flow(
            cashflow_df, period_col
        )
        cashflow["net_cash_change"] = _pick_net_cash_change(cashflow_df, period_col)

        ocf = cashflow["operating_cash_flow"].value
        capex = _pick_capex(cashflow_df, period_col)
        if ocf is not None and capex is not None:
            cashflow["free_cash_flow"] = _make_cell(
                "free_cash_flow",
                ocf - abs(capex),
                xbrl_tag="derived_fcf",
                label="OCF − |CapEx|",
                source_statement="cashflow",
                source="derived",
            )
        else:
            cashflow["free_cash_flow"] = _make_cell(
                "free_cash_flow", None, source_statement="cashflow"
            )

    period = DetailedPeriod(
        fiscal_year=fy,
        fiscal_period="FY",
        period_end=period_end,
        income=income,
        balance=balance,
        cashflow=cashflow,
        is_bank_style=bank,
    )
    apply_detailed_derivations(period)
    return period


def _relative_diff(a: float, b: float) -> float:
    denom = max(abs(a), abs(b), 1.0)
    return abs(a - b) / denom


def run_integrity_checks(
    period: DetailedPeriod,
    *,
    balance_df: pd.DataFrame | None = None,
    cashflow_df: pd.DataFrame | None = None,
    period_col: str | None = None,
) -> list[str]:
    notes: list[str] = []
    b = period.balance
    ca = b.get("current_assets")
    nca = b.get("non_current_assets")
    cl = b.get("current_liabilities")
    ncl = b.get("non_current_liabilities")

    if (
        balance_df is not None
        and period_col
        and ca
        and nca
        and ca.value is not None
        and nca.value is not None
    ):
        total_val, _ = _pick_raw_tag(
            balance_df, period_col, "Assets", label_needles=("total assets",)
        )
        if total_val is not None and _relative_diff(ca.value + nca.value, total_val) > 0.02:
            notes.append(
                f"FY{period.fiscal_year}: current + non-current assets "
                f"({ca.value + nca.value:,.0f}) ≠ total assets ({total_val:,.0f})"
            )

    if (
        cl
        and ncl
        and cl.value is not None
        and ncl.value is not None
        and balance_df is not None
        and period_col
    ):
        total_val, _ = _pick_raw_tag(
            balance_df, period_col, "Liabilities", label_needles=("total liabilities",)
        )
        if total_val is not None and _relative_diff(cl.value + ncl.value, total_val) > 0.02:
            notes.append(
                f"FY{period.fiscal_year}: current + non-current liabilities "
                f"≠ total liabilities"
            )

    cf = period.cashflow
    ocf = cf.get("operating_cash_flow")
    cfi = cf.get("investing_cash_flow")
    cff = cf.get("financing_cash_flow")
    net = cf.get("net_cash_change")
    if (
        cashflow_df is not None
        and period_col
        and ocf
        and cfi
        and cff
        and net
        and ocf.value is not None
        and cfi.value is not None
        and cff.value is not None
        and net.value is not None
    ):
        fx_val, _ = _pick_raw_tag(
            cashflow_df,
            period_col,
            "EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        )
        fx = fx_val or 0.0
        summed = ocf.value + cfi.value + cff.value + fx
        if _relative_diff(summed, net.value) > 0.05:
            notes.append(
                f"FY{period.fiscal_year}: CFO+CFI+CFF+FX ({summed:,.0f}) "
                f"≠ net cash change ({net.value:,.0f})"
            )

    inc = period.income
    gp = inc.get("gross_profit")
    oi = inc.get("operating_income")
    oc = inc.get("operating_cost")
    if (
        gp
        and oi
        and oc
        and gp.value is not None
        and oi.value is not None
        and oc.value is not None
        and oc.source != "n/a"
    ):
        implied = gp.value - oi.value
        if _relative_diff(implied, oc.value) > 0.15:
            notes.append(
                f"FY{period.fiscal_year}: gross profit − operating income "
                f"({implied:,.0f}) differs from operating cost ({oc.value:,.0f})"
            )

    if period.accounting_equation_ok is False:
        ta = b.get("total_assets")
        tl = b.get("total_liabilities")
        eq = b.get("stockholders_equity")
        if ta and tl and eq and ta.value and tl.value and eq.value:
            notes.append(
                f"FY{period.fiscal_year}: total assets ({ta.value:,.0f}) "
                f"≠ liabilities + equity ({tl.value + eq.value:,.0f})"
            )

    return notes


def build_detailed_snapshot(
    *,
    ticker: str,
    entity_name: str,
    cik: str,
    fetched_at: str,
    source: str,
    income_df: pd.DataFrame | None,
    balance_df: pd.DataFrame | None,
    cashflow_df: pd.DataFrame | None,
    fy_end_mmdd: str | None = None,
    max_periods: int = 5,
    warnings: list[str] | None = None,
) -> DetailedAnalysisSnapshot:
    cols: set[str] = set()
    for df in (income_df, balance_df, cashflow_df):
        if df is not None:
            cols.update(period_columns(df))
    ordered = sorted(cols, key=period_end_from_col, reverse=True)[:max_periods]

    periods: list[DetailedPeriod] = []
    integrity: list[str] = []
    is_bank = False
    for col in ordered:
        period = extract_detailed_period(
            income_df,
            balance_df,
            cashflow_df,
            col,
            fy_end_mmdd=fy_end_mmdd,
        )
        periods.append(period)
        if period.is_bank_style:
            is_bank = True
        integrity.extend(
            run_integrity_checks(
                period,
                balance_df=balance_df,
                cashflow_df=cashflow_df,
                period_col=col,
            )
        )

    if ticker.upper() in KNOWN_BANK_TICKERS:
        is_bank = True

    return DetailedAnalysisSnapshot(
        ticker=ticker,
        entity_name=entity_name,
        cik=cik,
        fetched_at=fetched_at,
        source=source,
        periods=periods,
        warnings=warnings or [],
        integrity_checks=integrity,
        is_bank_style=is_bank,
    )


def _line_item_to_cell(li: Any, key: str) -> MetricCell:
    from ingest.normalize import LineItem

    if not isinstance(li, LineItem):
        return MetricCell(key=key, value=None)
    warning = getattr(li, "warning", None)
    return MetricCell(
        key=li.key,
        value=li.value,
        xbrl_tag=li.xbrl_tag,
        label=li.label,
        source=li.source if li.source in ("xbrl", "derived") else "xbrl",
        warning=warning,
    )


def _period_cells_from_slice(
    slice_: Any | None,
    fiscal_year: int,
    order: tuple[str, ...],
    stmt_name: str,
) -> dict[str, MetricCell]:
    cells: dict[str, MetricCell] = {k: MetricCell(key=k) for k in order}
    if not slice_:
        return cells
    match = next((p for p in slice_.annual if p.fiscal_year == fiscal_year), None)
    if not match:
        return cells
    by_key = {li.key: li for li in match.line_items}
    for key in order:
        li = by_key.get(key)
        if li is not None:
            cell = _line_item_to_cell(li, key)
            cell.source_statement = stmt_name
            cells[key] = cell
    return cells


def build_detailed_snapshot_from_financials(
    financials: Any,
    *,
    max_periods: int = 5,
) -> DetailedAnalysisSnapshot:
    """Build detailed analysis snapshot from materialized FinancialStatements."""
    from ingest.normalize import FinancialStatements

    if not isinstance(financials, FinancialStatements):
        financials = FinancialStatements.model_validate(financials)

    income_slice = financials.statements.get("income")
    years: list[int] = []
    if income_slice:
        years = sorted({p.fiscal_year for p in income_slice.annual}, reverse=True)
    if not years:
        for slice_ in financials.statements.values():
            years = sorted({p.fiscal_year for p in slice_.annual}, reverse=True)
            if years:
                break
    years = years[:max_periods]

    periods: list[DetailedPeriod] = []
    integrity: list[str] = []
    is_bank = financials.ticker.upper() in KNOWN_BANK_TICKERS

    for fy in years:
        inc = _period_cells_from_slice(
            financials.statements.get("income"), fy, DETAILED_INCOME_ORDER, "income"
        )
        bal = _period_cells_from_slice(
            financials.statements.get("balance"), fy, DETAILED_BALANCE_ORDER, "balance"
        )
        cf = _period_cells_from_slice(
            financials.statements.get("cashflow"), fy, DETAILED_CASHFLOW_ORDER, "cashflow"
        )
        period_end = ""
        for slice_ in financials.statements.values():
            if not slice_:
                continue
            match = next((p for p in slice_.annual if p.fiscal_year == fy), None)
            if match and match.period_end:
                period_end = match.period_end
                break

        period = DetailedPeriod(
            fiscal_year=fy,
            fiscal_period="FY",
            period_end=period_end or f"{fy}-12-31",
            income=inc,
            balance=bal,
            cashflow=cf,
        )
        if not is_bank:
            rev = inc.get("revenue")
            cogs = inc.get("cost_of_revenue")
            gp = inc.get("gross_profit")
            if (
                rev
                and rev.value is not None
                and (not cogs or cogs.value is None)
                and (not gp or gp.value is None)
            ):
                period.is_bank_style = True
                is_bank = True
        _update_accounting_equation_flag(period)
        integrity.extend(run_integrity_checks(period))
        periods.append(period)

    return DetailedAnalysisSnapshot(
        ticker=financials.ticker,
        entity_name=financials.entity_name,
        cik=financials.cik,
        fetched_at=financials.fetched_at,
        source=financials.ingest_source or "cache",
        periods=periods,
        warnings=[],
        integrity_checks=integrity,
        is_bank_style=is_bank,
    )


def detailed_line_items_by_statement(
    period: DetailedPeriod,
) -> dict[str, list[dict[str, Any]]]:
    """Map detailed cells into per-statement line item dicts for ingest merge."""
    out: dict[str, list[dict[str, Any]]] = {
        "income": [],
        "balance": [],
        "cashflow": [],
    }
    for key in DETAILED_INCOME_ORDER:
        cell = period.income.get(key)
        if cell and cell.source != "n/a" and cell.value is not None:
            out["income"].append(cell.to_line_item())
    for key in DETAILED_BALANCE_ORDER:
        cell = period.balance.get(key)
        if cell and cell.value is not None:
            out["balance"].append(cell.to_line_item())
    for key in DETAILED_CASHFLOW_ORDER:
        cell = period.cashflow.get(key)
        if cell and cell.value is not None:
            out["cashflow"].append(cell.to_line_item())
    return out


def merge_detailed_into_line_items(
    by_stmt: dict[str, list[Any]],
    period: DetailedPeriod,
) -> None:
    """Merge detailed metrics into existing line items (detailed wins on key collision)."""
    from ingest.normalize import LineItem

    detailed = detailed_line_items_by_statement(period)
    for stmt, items in detailed.items():
        if stmt not in by_stmt:
            continue
        existing_list = by_stmt.get(stmt, [])
        by_key = {li.key: li for li in existing_list}
        for item in items:
            key = item["key"]
            payload = {k: v for k, v in item.items() if k in LineItem.model_fields}
            if key in by_key:
                merged = {**by_key[key].model_dump(), **payload}
                by_key[key] = LineItem(**merged)
            else:
                by_key[key] = LineItem(**payload)
        by_stmt[stmt] = list(by_key.values())
