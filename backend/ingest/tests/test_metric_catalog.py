"""Tests for canonical metric catalog."""

from ingest.metric_catalog import (
    METRICS,
    METRICS_BY_KEY,
    STATEMENT_METRIC_ORDER,
    metrics_for_statement,
)


def test_all_statements_have_metrics():
    for stmt in ("income", "balance", "cashflow"):
        assert len(metrics_for_statement(stmt)) > 0


def test_net_income_includes_profit_loss_alias():
    ni = METRICS_BY_KEY["net_income"]
    tags = [(a.namespace, a.tag) for a in ni.aliases]
    assert ("us-gaap", "ProfitLoss") in tags
    assert ("us-gaap", "NetIncomeLoss") in tags


def test_shares_includes_dei():
    sh = METRICS_BY_KEY["shares_outstanding"]
    tags = [(a.namespace, a.tag) for a in sh.aliases]
    assert ("dei", "EntityCommonStockSharesOutstanding") in tags


def test_statement_order_covers_core_keys():
    income_keys = set(STATEMENT_METRIC_ORDER["income"])
    for key in ("revenue", "operating_income", "net_income", "ebitda"):
        assert key in income_keys


def test_metric_count():
    assert len(METRICS) >= 25
