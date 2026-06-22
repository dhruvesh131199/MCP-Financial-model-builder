"""Tests for SEC scope_applied summary and MCP instruction content."""

from ingest.normalize import FinancialStatements, StatementPeriod, StatementSlice
from services.sec_financials import build_scope_applied, financials_summary


def _sample_financials() -> FinancialStatements:
    return FinancialStatements(
        ticker="AAPL",
        cik="0000320193",
        entity_name="Apple Inc.",
        fetched_at="2026-01-01T00:00:00Z",
        ingest_source="edgartools",
        statements={
            "income": StatementSlice(
                annual=[
                    StatementPeriod(
                        fiscal_year=2023,
                        fiscal_period="FY",
                        period_end="2023-09-30",
                        line_items=[],
                    )
                ],
                quarterly=[
                    StatementPeriod(
                        fiscal_year=2023,
                        fiscal_period="Q2",
                        period_end="2023-04-01",
                        line_items=[],
                    )
                ],
            )
        },
        fetch_scope=["income"],
    )


def test_build_scope_applied_echoes_request_and_result():
    fin = _sample_financials()
    scope = build_scope_applied(
        fiscal_years=[2023],
        max_years=1,
        include_annual=True,
        include_quarterly=True,
        statements=["income"],
        financials=fin,
    )
    assert scope["fiscal_years_requested"] == [2023]
    assert scope["fiscal_years_included"] == [2023]
    assert scope["quarterly_fiscal_years_included"] == [2023]
    assert scope["annual_period_count"] == 1
    assert scope["quarterly_period_count"] == 1


def test_financials_summary_includes_scope_applied():
    fin = _sample_financials()
    scope = build_scope_applied(
        fiscal_years=[2023],
        max_years=1,
        include_annual=True,
        include_quarterly=False,
        statements=["income"],
        financials=fin,
    )
    summary = financials_summary(fin, scope_applied=scope)
    assert summary["scope_applied"]["fiscal_years_included"] == [2023]


def test_mcp_instructions_contain_phrase_mapping():
    from pathlib import Path

    text = Path(__file__).resolve().parents[1].joinpath("mcp", "server.py").read_text()
    assert "Fetch Apple reports" in text
    assert "fiscal_years=[2023]" in text
    assert "scope_applied" in text


def test_fetch_sec_financials_docstring_contains_examples():
    from pathlib import Path

    text = Path(__file__).resolve().parents[1].joinpath("mcp", "server.py").read_text()
    assert "USER PHRASE" in text
    assert "scope_applied" in text
    assert "include_quarterly=false" in text
