# SEC normalization rules

How filed XBRL becomes dashboard line items.

## Primary path (edgartools statements)

| Step | What happens |
|------|----------------|
| 1 | Select 10-K / 10-Q filings (metadata scan; `amendments=False`) |
| 2 | `Financials.extract(filing)` → `income_statement()` / `balance_sheet()` / `cashflow_statement()` |
| 3 | `ingest/statement_extract.py` — total-line rules + `standard_concept` mapping |
| 4 | `FinancialStatements` JSON in session Files |

Default latest annual uses `company.get_financials()` (one fast 10-K). Multi-year / quarterly uses one statement parse per filing — **no XBRLS stitch**.

## Fallback

If edgartools fails, `services/sec_financials.py` falls back to SEC `companyfacts` API + `ingest/normalize.py`.

## Key extraction rules

- **Revenue:** prefer `RevenuesNetOfInterestExpense` / `Revenues` total lines; do not trust lone `standard_concept=Revenue` on banks (JPM principal transactions). For `Revenues`, accept labels like **“Total net sales and revenue”** (GM) before segment `RevenueFromContract…` lines.
- **Balance totals:** pick row labeled “Total assets” / largest `Assets` row — not first sub-asset line.
- **Operating cash flow:** pick total OCF line, not adjustment sub-lines.
- **Investing / financing cash flow:** use raw tags `NetCashProvidedByUsedInInvestingActivities` and `NetCashProvidedByUsedInFinancingActivities` only — never trust `standard_concept` alone (sub-lines like "Other" or "Deposits" share the same bucket).
- **Net cash change:** `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect` or `NetChangeInCash`.
- **Balance sections:** `AssetsCurrent` / `AssetsNoncurrent` / `LiabilitiesCurrent` / `LiabilitiesNoncurrent` total lines with label guards — not largest row by `standard_concept`.
- **Operating cost:** `OperatingExpenses` total label → `TotalOperatingExpenses` → sum R&D+SG&A → bank `NoninterestExpense`.
- **Detailed analysis:** `ingest/detailed_extract.py` — curated 5-year template for dashboard Detailed Analysis panel + homework `homework/detailed_analysis/`.
  - **COGS (conglomerate):** when automotive `CostOfGoodsAndServicesSold` exists alongside GM Financial `OperatingCostsAndExpenses`, sum both (`conglomerate_cogs_sum`) — do not return automotive-only on first single COGS row.
  - **Operating cost:** reject `OperatingExpenses` rows labeled *“Total costs and expenses”* (GM’s full cost block); prefer SG&A alone or derive `gross_profit − operating_income`.
  - **Derived fallbacks:** gross profit (`revenue − |COGS|`), non-current assets/liabilities (`total − current`), EBITDA (`operating_income + D&A`), CF D&A sum when filer uses extension tags (GM).
  - **Balance totals:** `total_assets`, `total_liabilities`, `cash_end_of_period`; integrity flag when `|A − (L + E)| / A > 2%`.
- **Session statements cache (Phase 2):** `inputs/statements.json` — `tickers.{TICKER}.periods.{FY2025|Q1_2026}.statements.{income|balance|cashflow}`; incremental fetch via `compute_fetch_gaps`; Files panel materialized from cache.
- **COGS (Files ingest):** when multiple `CostOfGoodsAndServicesSold` rows, prefer `CostOfGoodsAndServicesSold` tag over excluding-D&A variant (never sum).
- **No derived metrics** in Files (no EBITDA/FCF synthesis) — XBRL only.

## Fiscal year labels

`ingest/fiscal_calendar.py` maps `period_of_report` + company `fiscal_year_end` to FY / Q1–Q4.

## Dedup key

`ingest=edgartools|fetch=statements` — repeat fetch with same scope updates the sidebar file.
