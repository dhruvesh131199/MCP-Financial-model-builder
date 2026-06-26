"""Extract canonical metrics from edgartools statement DataFrames."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from ingest.concept_map import LINE_LABELS, STATEMENT_METRIC_ORDER
from ingest.edgar_concept_map import (
    STANDARD_CONCEPT_TAG_PRIORITY,
    STANDARD_CONCEPT_TO_KEY,
    tag_priority_rank,
)
from ingest.metric_catalog import METRICS_BY_KEY

SEGMENT_LABEL_RE = re.compile(
    r"segment|reconcil|corporate\b|international\b|geograph",
    re.IGNORECASE,
)
TOTAL_REVENUE_CONCEPTS = (
    "RevenuesNetOfInterestExpense",
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
)
TOTAL_LABEL_RE = re.compile(
    r"^total\s+(net\s+)?revenu|^total\s+revenue|"
    r"^net\s+revenues?$|"
    r"net\s+(sales|revenue|operating\s+revenues?)$|"
    r"^revenue$|^revenues$",
    re.IGNORECASE,
)

STATEMENT_METHODS = {
    "income": "income_statement",
    "balance": "balance_sheet",
    "cashflow": "cashflow_statement",
}

# standard_concept → canonical key (cashflow D&A override applied at extract time)
_CASHFLOW_SC_OVERRIDE = {"DepreciationExpense": "depreciation_and_amortization"}


def period_columns(df: pd.DataFrame) -> list[str]:
    cols: list[str] = []
    for col in df.columns:
        text = str(col).split("(")[0].strip()
        if len(text) >= 10 and text[4] == "-" and text[:4].isdigit():
            cols.append(str(col))
    return sorted(cols, key=lambda c: str(c).split("(")[0].strip(), reverse=True)


def period_end_from_col(period_col: str) -> str:
    return str(period_col).split("(")[0].strip()


def is_annual_column(period_col: str) -> bool:
    return "(FY)" in str(period_col).upper() or "FY" in str(period_col).upper()


def strip_tag(concept: Any) -> str:
    text = str(concept or "")
    for prefix in ("us-gaap_", "dei_", "srt_", "c_", "ifrs-full_"):
        if text.startswith(prefix):
            return text[len(prefix) :]
    return text


def _num(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _total_revenue_label_ok(label: str, tag: str) -> bool:
    """Label looks like company-wide total revenue (not a segment sub-line)."""
    text = label.strip()
    lower = text.lower()
    if TOTAL_LABEL_RE.search(text):
        return True
    if "net of interest" in lower:
        return True
    if lower in ("total revenue", "total net revenue"):
        return True
    # GM-style: "Total net sales and revenue (Note 3)" on us-gaap_Revenues
    if tag == "Revenues" and "total net sales" in lower and "revenue" in lower:
        return True
    return False


def smart_revenue(df: pd.DataFrame, period_col: str) -> tuple[float | None, str | None]:
    """Total revenue — banks need tag/label rules, not blind standard_concept."""
    for tag in TOTAL_REVENUE_CONCEPTS:
        for _, row in df.iterrows():
            if strip_tag(row.get("concept")) != tag:
                continue
            label = str(row.get("label") or "")
            if SEGMENT_LABEL_RE.search(label):
                continue
            if tag in ("RevenuesNetOfInterestExpense", "Revenues"):
                if not _total_revenue_label_ok(label, tag):
                    continue
            val = _num(row.get(period_col))
            if val is not None:
                return val, tag

    rows = df[df["standard_concept"] == "Revenue"]
    good: list[tuple[float, str]] = []
    for _, row in rows.iterrows():
        label = str(row.get("label") or "")
        if SEGMENT_LABEL_RE.search(label):
            continue
        tag = strip_tag(row.get("concept"))
        if tag == "PrincipalTransactionsRevenue" or "fee income" in label.lower():
            continue
        val = _num(row.get(period_col))
        if val is not None:
            good.append((val, tag))
    if len(good) == 1:
        return good[0]
    if good:
        val, tag = max(good, key=lambda x: abs(x[0]))
        return val, tag
    return None, None


def _pick_standard_concept(
    df: pd.DataFrame,
    period_col: str,
    standard_concept: str,
    *,
    label_needles: tuple[str, ...] = (),
    prefer_largest: bool = False,
) -> tuple[float | None, str | None]:
    rows = df[df["standard_concept"] == standard_concept]
    if rows.empty:
        return None, None

    ranked: list[tuple[int, float, str]] = []
    for _, row in rows.iterrows():
        label = str(row.get("label") or "").lower()
        if SEGMENT_LABEL_RE.search(label):
            continue
        val = _num(row.get(period_col))
        if val is None:
            continue
        tag = strip_tag(row.get("concept"))
        rank = tag_priority_rank(standard_concept, tag)
        if label_needles and not any(n in label for n in label_needles):
            if not prefer_largest:
                continue
        ranked.append((rank, val, tag))

    if not ranked:
        return None, None

    if prefer_largest:
        _, val, tag = max(ranked, key=lambda x: abs(x[1]))
        return val, tag

    ranked.sort(key=lambda x: (x[0], -abs(x[1])))
    return ranked[0][1], ranked[0][2]


def _pick_raw_tag(
    df: pd.DataFrame,
    period_col: str,
    tag: str,
    *,
    label_needles: tuple[str, ...] = (),
) -> tuple[float | None, str | None]:
    for _, row in df.iterrows():
        if strip_tag(row.get("concept")) != tag:
            continue
        label = str(row.get("label") or "").lower()
        if label_needles and not any(n in label for n in label_needles):
            continue
        val = _num(row.get(period_col))
        if val is not None:
            return val, tag
    return None, None


def _concepts_for_key(key: str, statement: str) -> tuple[str, ...]:
    if statement == "cashflow" and key == "depreciation_and_amortization":
        return ("DepreciationExpense", "DepreciationAndAmortization")
    if key == "net_income":
        return ("NetIncome", "ProfitLoss")
    if key == "stockholders_equity":
        return (
            "AllEquityBalance",
            "AllEquityBalanceIncludingMinorityInterest",
            "CommonEquity",
        )
    return tuple(
        sc
        for sc, mapped in STANDARD_CONCEPT_TO_KEY.items()
        if mapped == key
    )


def extract_statement_metrics(
    df: pd.DataFrame,
    period_col: str,
    statement: str,
) -> dict[str, dict[str, Any]]:
    """Map one statement DataFrame column → canonical metric dicts."""
    metrics: dict[str, dict[str, Any]] = {}
    order = STATEMENT_METRIC_ORDER.get(statement, ())

    for key in order:
        if key == "revenue" and statement == "income":
            val, tag = smart_revenue(df, period_col)
        elif key == "total_assets":
            val, tag = _pick_standard_concept(
                df, period_col, "Assets", label_needles=("total assets",), prefer_largest=True
            )
            if val is None:
                val, tag = _pick_raw_tag(df, period_col, "Assets", label_needles=("total",))
        elif key == "total_liabilities":
            val, tag = _pick_standard_concept(
                df,
                period_col,
                "Liabilities",
                label_needles=("total liabilities",),
                prefer_largest=True,
            )
        elif key == "stockholders_equity":
            val, tag = None, None
            for sc in _concepts_for_key(key, statement):
                val, tag = _pick_standard_concept(
                    df,
                    period_col,
                    sc,
                    label_needles=("total stockholders", "total shareholders", "total equity", "total"),
                )
                if val is not None:
                    break
        elif key == "operating_cash_flow":
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
                prefer_largest=True,
            )
            if val is None:
                val, tag = _pick_raw_tag(
                    df, period_col, "NetCashProvidedByUsedInOperatingActivities"
                )
        elif key == "capex":
            val, tag = _pick_standard_concept(
                df,
                period_col,
                "CapitalExpenses",
                label_needles=("capital", "property", "equipment"),
            )
            if val is None:
                val, tag = _pick_raw_tag(
                    df, period_col, "PaymentsToAcquirePropertyPlantAndEquipment"
                )
        elif key == "cost_of_revenue":
            val, tag = _pick_standard_concept(
                df, period_col, "CostOfGoodsAndServicesSold"
            )
        else:
            val, tag = None, None
            for sc in _concepts_for_key(key, statement):
                if statement == "cashflow":
                    mapped = _CASHFLOW_SC_OVERRIDE.get(sc, STANDARD_CONCEPT_TO_KEY.get(sc))
                    if mapped != key:
                        continue
                elif STANDARD_CONCEPT_TO_KEY.get(sc) != key:
                    continue
                val, tag = _pick_standard_concept(df, period_col, sc)
                if val is not None:
                    break
            if val is None:
                metric = METRICS_BY_KEY.get(key)
                if metric:
                    for alias in metric.aliases:
                        val, tag = _pick_raw_tag(df, period_col, alias.tag)
                        if val is not None:
                            break

        if val is not None:
            metrics[key] = {"value": val, "xbrl_tag": tag}

    return metrics


def metrics_to_line_items(
    metrics: dict[str, dict[str, Any]],
    statement: str,
) -> list[dict[str, Any]]:
    order = STATEMENT_METRIC_ORDER.get(statement, ())
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in order:
        if key not in metrics:
            continue
        seen.add(key)
        m = metrics[key]
        items.append(
            {
                "key": key,
                "label": LINE_LABELS.get(key, key),
                "value": m["value"],
                "unit": METRICS_BY_KEY[key].unit if key in METRICS_BY_KEY else "USD",
                "source": "xbrl",
                "xbrl_tag": m.get("xbrl_tag"),
            }
        )
    return items


def statement_to_dataframe(statement: Any, *, view: str = "standard") -> pd.DataFrame | None:
    if statement is None:
        return None
    try:
        return statement.to_dataframe(view=view)
    except TypeError:
        try:
            return statement.to_dataframe()
        except Exception:
            return None
    except Exception:
        return None
