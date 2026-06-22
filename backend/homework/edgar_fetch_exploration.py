"""
Homework: compare edgartools financial-data APIs vs our ingest pipeline.

Run from backend/:
    python -m homework.edgar_fetch_exploration
    python -m homework.edgar_fetch_exploration --tickers JPM,BAC,AAPL
    python -m homework.edgar_fetch_exploration --metric net_income

Goal: find a consistent, accurate way to fetch key metrics without brittle
custom maps. edgartools *does* standardize aliases — but standard_concept and
get_revenue() are not reliable for banks (and sometimes duplicate Revenue rows).

See: https://edgartools.readthedocs.io/en/latest/guides/financial-data/
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd
from dotenv import load_dotenv
from edgar import Company

load_dotenv()

from ingest.edgar_identity import ensure_edgar_identity  # noqa: E402

# ---------------------------------------------------------------------------
# Tickers: mix of banks, tech, payments, brokers — where revenue tagging varies
# ---------------------------------------------------------------------------
DEFAULT_TICKERS = [
    "AAPL",
    "MSFT",
    "AMD",
    "JPM",
    "BAC",
    "C",
    "WFC",
    "GS",
    "MS",
    "V",
    "MA",
    "KO",
    "XOM",
]

TOTAL_REVENUE_CONCEPTS = (
    "RevenuesNetOfInterestExpense",
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
)

SEGMENT_LABEL_RE = re.compile(
    r"segment|reconcil|corporate\b|international\b|geograph",
    re.IGNORECASE,
)
TOTAL_LABEL_RE = re.compile(
    r"^total\s+(net\s+)?revenu|^total\s+revenue|"
    r"^net\s+revenues?$|"
    r"net\s+(sales|revenue|operating\s+revenues?)$|"
    r"^revenue$|^revenues$",
    re.IGNORECASE,
)


def _period_cols(df: pd.DataFrame) -> list[str]:
    cols = [
        str(c)
        for c in df.columns
        if len(str(c).split("(")[0].strip()) >= 10
        and str(c).split("(")[0].strip()[4] == "-"
        and str(c).split("(")[0].strip()[:4].isdigit()
    ]
    return sorted(cols, key=lambda c: str(c).split("(")[0].strip(), reverse=True)


def _strip_tag(concept: Any) -> str:
    text = str(concept or "")
    for prefix in ("us-gaap_", "dei_", "srt_"):
        if text.startswith(prefix):
            return text[len(prefix) :]
    return text


def _num(val: Any) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def fmt_b(v: float | None) -> str:
    if v is None:
        return "—"
    return f"${v / 1e9:.2f}B"


def fmt_pct(ref: float | None, got: float | None) -> str:
    if ref is None or got is None or ref == 0:
        return "?"
    err = abs(got - ref) / abs(ref)
    if err < 0.02:
        return "OK"
    if err < 0.10:
        return f"~{err * 100:.0f}% off"
    return f"BAD {err * 100:.0f}%"


# ---------------------------------------------------------------------------
# Reference ("what the filing face statement shows as total revenue")
# ---------------------------------------------------------------------------
def reference_total_revenue(df: pd.DataFrame, period_col: str) -> tuple[float | None, str]:
    """Best-effort ground truth from income statement DataFrame."""
    candidates: list[tuple[int, float, str]] = []

    for _, row in df.iterrows():
        val = _num(row.get(period_col))
        if val is None or abs(val) < 1e6:
            continue
        tag = _strip_tag(row.get("concept"))
        label = str(row.get("label") or "")
        sc = row.get("standard_concept")

        # Banks: total line often has no standard_concept
        if tag in ("RevenuesNetOfInterestExpense", "Revenues"):
            if SEGMENT_LABEL_RE.search(label):
                continue
            if TOTAL_LABEL_RE.search(label.strip()) or "net of interest" in label.lower():
                rank = 0 if tag == "RevenuesNetOfInterestExpense" else 1
                candidates.append((rank, val, f"{tag} | {label[:50]}"))

        # Non-banks: single Revenue standard_concept row
        if sc == "Revenue" and not SEGMENT_LABEL_RE.search(label):
            if TOTAL_LABEL_RE.search(label.strip()) or tag in TOTAL_REVENUE_CONCEPTS:
                candidates.append((2, val, f"sc=Revenue {tag} | {label[:40]}"))

    if not candidates:
        return None, "not found"

    candidates.sort(key=lambda x: (x[0], -abs(x[1])))
    _, val, note = candidates[0]
    return val, note


def reference_net_income(df: pd.DataFrame, period_col: str) -> tuple[float | None, str]:
    for _, row in df.iterrows():
        if row.get("standard_concept") in ("NetIncome", "ProfitLoss"):
            val = _num(row.get(period_col))
            if val is not None:
                tag = _strip_tag(row.get("concept"))
                return val, f"{tag} | {str(row.get('label',''))[:40]}"
    for tag in ("NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"):
        for _, row in df.iterrows():
            if _strip_tag(row.get("concept")) == tag:
                val = _num(row.get(period_col))
                if val is not None:
                    return val, tag
    return None, "not found"


# ---------------------------------------------------------------------------
# Extraction methods to compare
# ---------------------------------------------------------------------------
def method_getter(financials: Any, period_offset: int = 0) -> float | None:
    return _num(financials.get_revenue(period_offset=period_offset))


def method_get_financial_metrics(financials: Any, period_offset: int = 0) -> float | None:
    if period_offset != 0:
        return None  # metrics dict has no offset — document limitation
    m = financials.get_financial_metrics()
    return _num(m.get("revenue"))


def method_standard_concept_first(df: pd.DataFrame, period_col: str) -> float | None:
    """What our adapter does today for Revenue standard_concept."""
    rows = df[df["standard_concept"] == "Revenue"]
    for _, row in rows.iterrows():
        val = _num(row.get(period_col))
        if val is not None:
            return val
    return None


def method_raw_total_tags(df: pd.DataFrame, period_col: str) -> float | None:
    """Prefer total revenue XBRL tags without relying on standard_concept."""
    for tag in TOTAL_REVENUE_CONCEPTS:
        for _, row in df.iterrows():
            if _strip_tag(row.get("concept")) != tag:
                continue
            label = str(row.get("label") or "")
            if SEGMENT_LABEL_RE.search(label):
                continue
            if tag in ("RevenuesNetOfInterestExpense", "Revenues"):
                if not (
                    TOTAL_LABEL_RE.search(label.strip())
                    or "net of interest" in label.lower()
                    or label.strip().lower() in ("total revenue", "total net revenue")
                ):
                    continue
            val = _num(row.get(period_col))
            if val is not None:
                return val
    return None


def method_summary_label(df: pd.DataFrame, period_col: str) -> float | None:
    """Use summary view labels — matches SEC viewer top lines."""
    for _, row in df.iterrows():
        label = str(row.get("label") or "").strip()
        if not TOTAL_LABEL_RE.search(label) and "total revenue" not in label.lower():
            continue
        if SEGMENT_LABEL_RE.search(label):
            continue
        val = _num(row.get(period_col))
        if val is not None:
            return val
    return None


def method_smart_revenue(df: pd.DataFrame, period_col: str) -> float | None:
    """
    Prototype: raw total tags first, then standard_concept only if unique total-like row.
    """
    raw = method_raw_total_tags(df, period_col)
    if raw is not None:
        return raw

    rows = df[df["standard_concept"] == "Revenue"]
    good: list[float] = []
    for _, row in rows.iterrows():
        label = str(row.get("label") or "")
        if SEGMENT_LABEL_RE.search(label):
            continue
        tag = _strip_tag(row.get("concept"))
        if tag == "PrincipalTransactionsRevenue":
            continue  # bank sub-line, not total
        if "fee income" in label.lower():
            continue
        val = _num(row.get(period_col))
        if val is not None:
            good.append(val)
    if len(good) == 1:
        return good[0]
    if good:
        return max(good)  # if multiple totals tagged Revenue (e.g. C), take largest
    return None


METHODS: dict[str, Callable[..., float | None]] = {
    "get_revenue()": method_getter,
    "get_financial_metrics": method_get_financial_metrics,
    "standard_concept=Revenue (ours)": method_standard_concept_first,
    "raw_total_tags": method_raw_total_tags,
    "summary_label": method_summary_label,
    "smart_revenue (proto)": method_smart_revenue,
}


@dataclass
class RowResult:
    ticker: str
    reference: float | None
    ref_note: str
    values: dict[str, float | None]


def explore_ticker(ticker: str, *, period_offset: int = 0) -> RowResult:
    company = Company(ticker)
    financials = company.get_financials()
    income = financials.income_statement(view="standard")
    df_std = income.to_dataframe(view="standard")
    df_sum = financials.income_statement(view="summary").to_dataframe(view="summary")

    cols = _period_cols(df_std)
    if not cols:
        return RowResult(ticker, None, "no periods", {k: None for k in METHODS})

    period_col = cols[period_offset] if period_offset < len(cols) else cols[0]
    ref, ref_note = reference_total_revenue(df_std, period_col)

    values: dict[str, float | None] = {}
    values["get_revenue()"] = method_getter(financials, period_offset)
    values["get_financial_metrics"] = method_get_financial_metrics(financials, period_offset)
    values["standard_concept=Revenue (ours)"] = method_standard_concept_first(df_std, period_col)
    values["raw_total_tags"] = method_raw_total_tags(df_std, period_col)
    values["summary_label"] = method_summary_label(df_sum, period_col)
    values["smart_revenue (proto)"] = method_smart_revenue(df_std, period_col)

    return RowResult(ticker, ref, ref_note, values)


def print_revenue_report(results: list[RowResult]) -> None:
    methods = list(METHODS.keys())
    print("\n=== REVENUE COMPARISON (latest annual 10-K) ===\n")
    print(f"{'ticker':6} {'reference':>12} ", end="")
    for m in methods:
        short = m.split("(")[0].strip()[:14]
        print(f"{short:>16}", end="")
    print()
    print("-" * (20 + 16 * len(methods)))

    scores = {m: {"ok": 0, "bad": 0, "na": 0} for m in methods}

    for r in results:
        print(f"{r.ticker:6} {fmt_b(r.reference):>12} ", end="")
        for m in methods:
            v = r.values.get(m)
            status = fmt_pct(r.reference, v)
            if r.reference is None or v is None:
                scores[m]["na"] += 1
            elif status == "OK":
                scores[m]["ok"] += 1
            else:
                scores[m]["bad"] += 1
            cell = fmt_b(v) if v is not None else "—"
            print(f"{cell:>16}", end="")
        print()

    print("\n--- Accuracy vs reference ---")
    for m in methods:
        s = scores[m]
        total = s["ok"] + s["bad"]
        pct = f"{100 * s['ok'] / total:.0f}%" if total else "n/a"
        print(f"  {m:40} OK={s['ok']:2} BAD={s['bad']:2} missing={s['na']:2}  hit_rate={pct}")

    print("\n--- Reference notes (banks / edge cases) ---")
    for r in results:
        if r.reference is not None:
            print(f"  {r.ticker}: {fmt_b(r.reference)} ← {r.ref_note}")


def explore_net_income(tickers: list[str]) -> None:
    print("\n=== NET INCOME (get_net_income vs reference) ===\n")
    print(f"{'ticker':6} {'reference':>12} {'get_net_income':>16} {'status':>10}")
    print("-" * 50)
    ok = bad = 0
    for t in tickers:
        c = Company(t)
        fin = c.get_financials()
        df = fin.income_statement().to_dataframe()
        cols = _period_cols(df)
        if not cols:
            continue
        ref, _ = reference_net_income(df, cols[0])
        got = _num(fin.get_net_income())
        st = fmt_pct(ref, got)
        if st == "OK":
            ok += 1
        elif ref and got:
            bad += 1
        print(f"{t:6} {fmt_b(ref):>12} {fmt_b(got):>16} {st:>10}")
    total = ok + bad
    print(f"\n  get_net_income hit rate: {ok}/{total} ({100*ok/total:.0f}%)" if total else "")


def explore_period_offset(ticker: str = "AAPL") -> None:
    print(f"\n=== period_offset on {ticker} (revenue) ===\n")
    c = Company(ticker)
    fin = c.get_financials()
    df = fin.income_statement().to_dataframe()
    cols = _period_cols(df)
    for i in range(min(3, len(cols))):
        col = cols[i]
        ref, _ = reference_total_revenue(df, col)
        getter = _num(fin.get_revenue(period_offset=i))
        smart = method_smart_revenue(df, col)
        print(
            f"  offset={i} period={col[:10]}  ref={fmt_b(ref)}  "
            f"get_revenue={fmt_b(getter)}  smart={fmt_b(smart)}  "
            f"getter={fmt_pct(ref, getter)}  smart={fmt_pct(ref, smart)}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Explore edgartools financial fetch methods")
    parser.add_argument("--tickers", default=",".join(DEFAULT_TICKERS))
    parser.add_argument("--metric", choices=["revenue", "net_income", "all"], default="all")
    parser.add_argument("--offset-demo", action="store_true", help="Show period_offset demo on AAPL")
    args = parser.parse_args()

    ensure_edgar_identity()
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    print("edgartools homework — financial data API exploration")
    print("Docs: https://edgartools.readthedocs.io/en/latest/guides/financial-data/")
    print(f"Tickers: {', '.join(tickers)}\n")

    if args.metric in ("revenue", "all"):
        results = [explore_ticker(t) for t in tickers]
        print_revenue_report(results)

    if args.metric in ("net_income", "all"):
        explore_net_income(tickers)

    if args.offset_demo or args.metric == "all":
        explore_period_offset("AAPL")

    print("\n=== TAKEAWAYS ===")
    print(
        """
1. edgartools DOES standardize via standard_concept + get_*() helpers — but
   standardization is INCOMPLETE for banks:
   - Total revenue (RevenuesNetOfInterestExpense / Revenues) often has NO standard_concept
   - standard_concept='Revenue' may point at a sub-line (principal transactions, fee income)

2. get_revenue() and get_financial_metrics()['revenue'] use the same standardization
   store — they fail on JPM/C/WFC the same way our adapter does (sometimes differently).

3. For multi-year / multi-quarter comps we still need XBRLS stitch OR per-filing fetch;
   getters only cover latest filing periods (period_offset is per-statement columns).

4. Prototype smart_revenue: prefer total revenue XBRL tags + label filters, don't blindly
   trust standard_concept='Revenue'. This is a SMALL rule on top of edgartools DataFrames,
   not a full custom concept map.

5. We likely DON'T need a large edgar_concept_map if we:
   - Use edgartools DataFrames as source of truth
   - Add priority rules for known total-line tags (RevenuesNetOfInterestExpense, Revenues)
   - Keep RAW_TAG_TO_KEY as fallback for unstandardized rows
   - Use get_net_income() etc. where standardization works (net income is solid)
"""
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
