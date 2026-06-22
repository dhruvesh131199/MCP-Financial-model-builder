"""GAAP XBRL tag aliases → canonical statement line items (derived from metric_catalog)."""

from ingest.metric_catalog import (
    BALANCE_METRIC_ORDER,
    CASHFLOW_METRIC_ORDER,
    INCOME_METRIC_ORDER,
    STATEMENT_METRIC_ORDER,
    line_labels,
    statement_concepts_legacy,
)

_STATEMENT_CONCEPTS = statement_concepts_legacy()

INCOME_CONCEPTS = _STATEMENT_CONCEPTS["income"]
BALANCE_CONCEPTS = _STATEMENT_CONCEPTS["balance"]
CASHFLOW_CONCEPTS = _STATEMENT_CONCEPTS["cashflow"]

STATEMENT_CONCEPTS = _STATEMENT_CONCEPTS
LINE_LABELS = line_labels()

__all__ = [
    "INCOME_CONCEPTS",
    "BALANCE_CONCEPTS",
    "CASHFLOW_CONCEPTS",
    "STATEMENT_CONCEPTS",
    "LINE_LABELS",
    "STATEMENT_METRIC_ORDER",
    "INCOME_METRIC_ORDER",
    "BALANCE_METRIC_ORDER",
    "CASHFLOW_METRIC_ORDER",
]
