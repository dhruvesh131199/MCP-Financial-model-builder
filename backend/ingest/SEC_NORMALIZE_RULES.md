# SEC financial normalization — business rules

Authoritative rules for turning SEC EDGAR data into session file `FinancialStatements`.
Python implements these exactly; the host LLM never does financial arithmetic.

## Data source (primary vs fallback)

| Priority | Source | Module |
|----------|--------|--------|
| 1 | **edgartools `XBRLS`** — stitch 10-K / 10-Q filings, `standard_concept` labels | `ingest/edgar_fetch.py`, `ingest/edgar_adapter.py` |
| 2 | SEC `companyfacts` JSON (fallback if XBRLS fails) | `services/sec_client.py`, `ingest/normalize.py` |

edgartools maps ~2,000 XBRL tags → 95 `standard_concept` values (see
`ingest/edgar_concept_map.py`). Period columns use fiscal **end dates** from stitched
filings (e.g. `2025-12-27`), not SEC’s filing `fy` field.

## Pipeline (four passes)

```
Pass 1 — COLLECT   Walk every metric alias; bucket each XBRL fact by reporting period
Pass 2 — SELECT    For each (metric, period), pick one fact (latest filing wins)
Pass 3 — ASSEMBLE  Build annual + quarterly StatementPeriod rows per statement
Pass 4 — DERIVE    Fill remaining canonical fields via accounting identities
```

Multiple loops are intentional: correctness over cleverness.

---

## Pass 1 — Period identification

A fact belongs to a **reporting period**, not to the filing’s `fy` field.

SEC tags comparative columns in a 10-K with the **same `fy`** (filing fiscal year)
while `start`/`end` identify the actual period. Bucketing by `fy` alone mis-assigns
historical years (AMD FY2023 showed FY2022 revenue).

### Period key

| Priority | Key source | Example |
|----------|------------|---------|
| 1 | `end` date + `fp` | `("2023-12-30", "FY")` |
| 2 | `frame` field | `CY2023` → FY2023, `CY2024Q1` → Q1 FY2024 |
| 3 | `fy` + `fp` (fixtures only) | Single-row buckets when `end` absent |

### Fiscal year label

`fiscal_year` = calendar year of the period **`end`** date (US GAAP convention for
display). Examples:

- AMD FY2023 ends `2023-12-30` → `fiscal_year = 2023`
- Visa FY2025 ends `2025-09-30` → `fiscal_year = 2025`

### Period types

- **Annual:** `fp == "FY"` or `form == "10-K"` with annual duration
- **Quarterly:** `fp in {Q1, Q2, Q3, Q4}` or `form == "10-Q"`
- **Balance sheet:** instant facts (`end` only, no `start`) — same period key rules

---

## Pass 2 — Fact selection (one value per metric per period)

When several XBRL facts map to the same `(metric, period_end, fp)`:

1. Prefer **`10-K`** over **`10-Q`** for annual (`FY`) periods
2. Prefer **`10-Q`** for quarterly periods when both exist
3. Among ties, pick the row with the **latest `filed`** date (most recent restatement)
4. **Never** select by largest absolute value — that picks the wrong comparative column

### Alias order

For each canonical metric, try aliases **in catalog order**. First alias that
yields a value for the period wins; later aliases are skipped for that period.

---

## Pass 3 — Canonical metrics (from `metric_catalog.py`)

### Income statement

`revenue`, `cost_of_revenue`, `gross_profit`, `research_and_development`,
`selling_general_admin`, `operating_income`, `depreciation`, `amortization`,
`ebitda`, `interest_expense`, `income_before_tax`, `income_tax_expense`,
`net_income`, `eps_basic`, `eps_diluted`, `weighted_avg_shares_basic`,
`weighted_avg_shares_diluted`, `shares_outstanding`

### Balance sheet

`cash`, `short_term_investments`, `total_assets`, `total_liabilities`,
`stockholders_equity`, `short_term_debt`, `long_term_debt`, `total_debt`,
`shares_outstanding`

### Cash flow

`operating_cash_flow`, `capex`, `free_cash_flow`

Missing XBRL tag → leave empty for Pass 4 (do not invent).

---

## Pass 4 — Derived fields (companyfacts fallback / tests only)

**EdgarTools session Files:** XBRL only — no Pass 4 derivations. Empty rows in dashboard.

When several rows share one `standard_concept`, pick one tag (prefer totals) — **never sum**.

| Field | Formula | Notes |
|-------|---------|-------|
| `revenue` | `gross_profit + abs(cost_of_revenue)` | When revenue tag absent |
| `gross_profit` | `revenue - abs(cost_of_revenue)` | |
| `net_income` | `eps_diluted × weighted_avg_shares_diluted` | |
| `eps_diluted` | `net_income / weighted_avg_shares_diluted` | shares > 0 |
| `shares_outstanding` | copy `weighted_avg_shares_diluted` | income statement fallback |
| `ebitda` | `operating_income + depreciation_and_amortization` | Combined D&A tag, or both separate D&A lines, or cash-flow D&A copied to income |
| | | Never default missing amortization to zero; omit EBITDA if add-back incomplete |
| `free_cash_flow` | `operating_cash_flow - abs(capex)` | |
| `total_debt` | `short_term_debt + long_term_debt` | When total debt tag absent |

Derivations set `source: "derived"` and `derived_from: [...]` for audit trail.

**Never derive** when a direct XBRL value already exists for that period.

---

## Coverage / missing values

- `not_applicable` — filer never reports the tag family (e.g. Visa COGS)
- `missing` — expected but not in XBRL and cannot derive
- `present` / `derived` — value available

---

## Validation target

For any ticker, annual FY columns must match the company’s **10-K** for that
period end (Yahoo annual columns are a reasonable cross-check). TTM columns on
aggregators are not comparable to our FY rows.
