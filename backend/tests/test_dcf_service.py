"""DCF draft service — projection years required, 5Y reference independent."""

from unittest.mock import patch

import pytest

from services.dcf_service import (
    DCF_REFERENCE_FETCH_YEARS,
    create_dcf_draft,
    compute_dcf_from_draft,
    summarize_dcf_draft,
    update_dcf_draft,
    validate_projection_years,
)
from store import create_session, get_model_entry


def _mock_financials():
    from ingest.normalize import FinancialStatements, StatementSlice, StatementPeriod, LineItem

    periods = []
    for fy in [2024, 2023, 2022, 2021, 2020]:
        rev = 10_000_000_000.0
        periods.append(
            StatementPeriod(
                fiscal_year=fy,
                fiscal_period="FY",
                form="10-K",
                line_items=[
                    LineItem(key="revenue", value=rev, label="Revenue"),
                    LineItem(key="ebitda", value=rev * 0.3, label="EBITDA"),
                    LineItem(key="capex", value=-rev * 0.05, label="CapEx"),
                    LineItem(key="income_before_tax", value=rev * 0.2, label="IBT"),
                    LineItem(key="income_tax_expense", value=rev * 0.04, label="Tax"),
                ],
            )
        )
    return FinancialStatements(
        ticker="MU",
        cik="0000723125",
        entity_name="Micron Technology",
        fetched_at="2024-01-01T00:00:00Z",
        statements={"income": StatementSlice(annual=periods, quarterly=[])},
    )


@pytest.fixture
def session_id():
    return create_session()


def test_projection_years_required():
    with pytest.raises(ValueError, match="projection_years is required"):
        validate_projection_years(None)


@patch("services.dcf_service.fetch_and_cache_statements")
@patch("services.dcf_service.resolve_ticker")
def test_create_draft_fetches_five_years(mock_resolve, mock_fetch, session_id):
    mock_resolve.return_value = {
        "ticker": "MU",
        "entity_name": "Micron Technology",
        "cik": "0000723125",
    }
    mock_fetch.return_value = (_mock_financials(), [], True, "file-1", "MU")

    result = create_dcf_draft(session_id, ticker="MU", projection_years=3)
    assert result["success"]
    assert result["projection_years"] == 3
    assert result["reference_years"] == 5

    mock_fetch.assert_called_once()
    assert mock_fetch.call_args.kwargs["max_years"] == DCF_REFERENCE_FETCH_YEARS

    entry = get_model_entry(session_id, result["model_id"])
    assert entry["type"] == "dcf_draft"
    data = entry["data"]
    assert len(data["inputs"]["revenue_growth"]) == 3
    assert len(data["reference_history"]["fiscal_years"]) == 5


@patch("services.dcf_service.fetch_and_cache_statements")
@patch("services.dcf_service.resolve_ticker")
def test_compute_draft_after_fill(mock_resolve, mock_fetch, session_id):
    mock_resolve.return_value = {"ticker": "MU", "entity_name": "Micron", "cik": "1"}
    mock_fetch.return_value = (_mock_financials(), [], True, "f1", "MU")

    created = create_dcf_draft(session_id, ticker="MU", projection_years=2)
    model_id = created["model_id"]

    update_dcf_draft(
        session_id,
        model_id,
        {
            "base_revenue": 1000.0,
            "wacc": 0.10,
            "terminal_growth": 0.02,
            "revenue_growth": [0.05, 0.05],
            "ebitda_margin": [0.30, 0.30],
            "tax_rate": [0.21, 0.21],
            "capex_pct": [0.05, 0.05],
            "nwc_pct": [0.02, 0.02],
        },
    )

    entry = get_model_entry(session_id, model_id)
    summary = summarize_dcf_draft(entry["data"])
    assert summary["ready"]

    computed = compute_dcf_from_draft(session_id, model_id)
    assert computed["success"]
    assert computed["enterprise_value_millions"] > 0

    computed2 = compute_dcf_from_draft(session_id, model_id)
    assert computed2["model_id"] == computed["model_id"]
