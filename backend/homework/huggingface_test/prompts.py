"""Prompt templates for HF income-statement normalization test."""

from __future__ import annotations

import json
from typing import Any

from homework.huggingface_test.fetch_income import IncomeBaseline, line_items_for_model

SYSTEM_PROMPT = """
You are an expert financial data normalizer. You are analyzing raw income statement data parsed from SEC Edgar filings.
The underlying tool (edgartools) has an initial baseline accuracy of roughly 93%, but your job is to find the remaining anomalies, resolve multi-tag conflicts, and elevate the data extraction to 100% precision.

You will be given a list of line items containing a 'label' (the text shown to humans), a 'concept' (the raw SEC XBRL tag), and a 'value'.

Your single task is to map these lines into these strict "standard_concept" buckets:
- Revenue
- Cost of goods sold
- Gross profit
- Operating expenses
- Operating income
- Interest expenses
- Tax
- Net income

Rules:
1. Identify and select the true top-line metrics. For example, if both a sub-component tag and a total tag exist, map the absolute mathematical total to the "standard_concept".
2. If a financial concept does not apply to this specific company structure (e.g., Gross Profit for a bank), map the rows that exist but omit the missing bucket.
3. You must output your response ONLY as a valid JSON array of objects. Do not include markdown code block syntax (```json), wrap it in markdown, or add conversational text.

The exact JSON format for every mapped item must be:
[
  {
    "tag": "wht we are looking for(Revenue, Net income, etc)",
    "label": "Human Readable Label",
    "concept": "raw_sec_xbrl_tag",
    "standard_concept": "standard_bucket_name",
    "value": 123456789
  }
]
""".strip()

STANDARD_BUCKETS = (
    "Revenue",
    "Cost of goods sold",
    "Gross profit",
    "Operating expenses",
    "Operating income",
    "Interest expenses",
    "Tax",
    "Net income",
)


def build_user_message(baseline: IncomeBaseline) -> str:
    items = line_items_for_model(baseline)
    payload = json.dumps(items, indent=2)
    fy = baseline.fiscal_year if baseline.fiscal_year else "unknown"
    return f"""Company: {baseline.entity_name} ({baseline.ticker})
CIK: {baseline.cik}
Fiscal year: FY{fy}
Period end: {baseline.period_end}
Filing date: {baseline.filing_date}

Line items (latest annual period only):
{payload}

Map these into the standard_concept buckets defined in your instructions. Output ONLY the JSON array.
"""


def build_chat_messages(baseline: IncomeBaseline) -> dict[str, str]:
    return {
        "system": SYSTEM_PROMPT,
        "user": build_user_message(baseline),
    }
