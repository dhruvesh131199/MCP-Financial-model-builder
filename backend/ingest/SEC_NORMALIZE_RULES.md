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

- **Revenue:** prefer `RevenuesNetOfInterestExpense` / `Revenues` total lines; do not trust lone `standard_concept=Revenue` on banks (JPM principal transactions).
- **Balance totals:** pick row labeled “Total assets” / largest `Assets` row — not first sub-asset line.
- **Operating cash flow:** pick total OCF line, not adjustment sub-lines.
- **COGS:** when multiple `CostOfGoodsAndServicesSold` rows, prefer `CostOfGoodsAndServicesSold` tag over excluding-D&A variant (never sum).
- **No derived metrics** in Files (no EBITDA/FCF synthesis) — XBRL only.

## Fiscal year labels

`ingest/fiscal_calendar.py` maps `period_of_report` + company `fiscal_year_end` to FY / Q1–Q4.

## Dedup key

`ingest=edgartools|fetch=statements` — repeat fetch with same scope updates the sidebar file.
