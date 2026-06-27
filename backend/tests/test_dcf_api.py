"""REST endpoints for DCF draft PATCH/POST."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from services.dcf_service import create_dcf_draft
from store import create_session
from tests.test_dcf_service import _mock_financials

client = TestClient(app)


@patch("services.dcf_service.fetch_and_cache_statements")
@patch("services.dcf_service.resolve_ticker")
def test_dcf_draft_patch_and_compute(mock_resolve, mock_fetch):
    sid = create_session()
    mock_resolve.return_value = {"ticker": "MU", "entity_name": "Micron", "cik": "1"}
    mock_fetch.return_value = (_mock_financials(), [], True, "f1", "MU")

    created = create_dcf_draft(sid, ticker="MU", projection_years=2)
    model_id = created["model_id"]

    patch_res = client.patch(
        f"/api/sessions/{sid}/models/{model_id}/dcf-draft",
        json={
            "base_revenue": 500.0,
            "wacc": 0.10,
            "terminal_growth": 0.02,
            "revenue_growth": [0.08, 0.06],
            "ebitda_margin": [0.28, 0.28],
            "tax_rate": [0.21, 0.21],
            "capex_pct": [0.04, 0.04],
            "nwc_pct": [0.02, 0.02],
        },
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["ready"] is True

    compute_res = client.post(f"/api/sessions/{sid}/models/{model_id}/dcf-compute")
    assert compute_res.status_code == 200
    body = compute_res.json()
    assert body["success"] is True
    assert body["enterprise_value_millions"] > 0
