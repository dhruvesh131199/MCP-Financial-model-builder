"""Per-year rate arrays in DCF engine."""

import pytest

from engine.dcf import DcfInputs, compute_dcf


def test_per_year_margins_change_ebitda():
    inputs = DcfInputs(
        base_revenue=100.0,
        revenue_growth=0.0,
        ebitda_margin=[0.20, 0.30, 0.40],
        da_pct=0.02,
        tax_rate=0.21,
        capex_pct=0.03,
        nwc_pct=0.02,
        wacc=0.10,
        terminal_growth=0.02,
        projection_years=3,
    )
    result = compute_dcf(inputs)
    assert result.years[0].ebitda == pytest.approx(20.0)
    assert result.years[1].ebitda == pytest.approx(30.0)
    assert result.years[2].ebitda == pytest.approx(40.0)


def test_per_year_tax_affects_fcf():
    inputs = DcfInputs(
        base_revenue=100.0,
        revenue_growth=0.0,
        ebitda_margin=0.25,
        da_pct=0.0,
        tax_rate=[0.10, 0.20, 0.30],
        capex_pct=0.0,
        nwc_pct=0.0,
        wacc=0.10,
        terminal_growth=0.02,
        projection_years=3,
    )
    result = compute_dcf(inputs)
    assert result.years[0].fcf == pytest.approx(22.5)
    assert result.years[1].fcf == pytest.approx(20.0)
    assert result.years[2].fcf == pytest.approx(17.5)


def test_rate_list_length_must_match_projection_years():
    with pytest.raises(ValueError, match="ebitda_margin"):
        DcfInputs(
            base_revenue=100.0,
            revenue_growth=0.10,
            ebitda_margin=[0.25, 0.25],
            da_pct=0.0,
            tax_rate=0.21,
            capex_pct=0.03,
            nwc_pct=0.02,
            wacc=0.10,
            terminal_growth=0.02,
            projection_years=5,
        )
