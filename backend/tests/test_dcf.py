"""Unit tests with hand-calculated DCF examples."""

import pytest

from engine.dcf import DcfInputs, compute_dcf


def _base_inputs(**overrides) -> DcfInputs:
    defaults = dict(
        base_revenue=100.0,
        revenue_growth=0.10,
        ebitda_margin=0.25,
        tax_rate=0.21,
        capex_pct=0.03,
        nwc_pct=0.02,
        wacc=0.10,
        terminal_growth=0.02,
        projection_years=5,
    )
    defaults.update(overrides)
    return DcfInputs(**defaults)


def test_year1_fcf():
    result = compute_dcf(_base_inputs())
    y1 = result.years[0]
    assert y1.year == 1
    assert y1.revenue == pytest.approx(110.0)
    assert y1.ebitda == pytest.approx(27.5)
    assert y1.fcf == pytest.approx(18.225)
    assert y1.pv_fcf == pytest.approx(18.225 / 1.1, rel=1e-4)


def test_five_year_projection():
    result = compute_dcf(_base_inputs())
    assert len(result.years) == 5
    assert result.years[4].revenue == pytest.approx(161.051, rel=1e-3)
    assert result.years[4].fcf == pytest.approx(26.6832, rel=1e-3)


def test_terminal_and_enterprise_value():
    result = compute_dcf(_base_inputs())
    final_fcf = result.years[-1].fcf
    terminal = final_fcf * 1.02 / (0.10 - 0.02)
    assert result.terminal_value == pytest.approx(terminal, rel=1e-3)
    assert result.pv_terminal == pytest.approx(terminal / 1.1**5, rel=1e-3)
    pv_sum = sum(y.pv_fcf for y in result.years)
    assert result.enterprise_value == pytest.approx(pv_sum + result.pv_terminal, rel=1e-4)


def test_equity_and_price_per_share():
    result = compute_dcf(_base_inputs(net_debt=20.0, shares_outstanding=50.0))
    assert result.equity_value == pytest.approx(result.enterprise_value - 20.0)
    assert result.price_per_share == pytest.approx(result.equity_value / 50.0)


def test_percent_normalization():
    result = compute_dcf(
        _base_inputs(
            revenue_growth=10,
            ebitda_margin=25,
            tax_rate=21,
            capex_pct=3,
            nwc_pct=2,
            wacc=10,
            terminal_growth=2,
        )
    )
    assert result.years[0].revenue == pytest.approx(110.0)


def test_per_year_growth_list():
    result = compute_dcf(
        _base_inputs(
            revenue_growth=[0.10, 0.10, 0.05, 0.05, 0.05],
            projection_years=5,
        )
    )
    assert result.years[0].revenue == pytest.approx(110.0)
    assert result.years[2].revenue == pytest.approx(127.05, rel=1e-3)


def test_wacc_must_exceed_terminal_growth():
    with pytest.raises(ValueError, match="WACC"):
        _base_inputs(wacc=0.02, terminal_growth=0.02)


def test_negative_revenue_rejected():
    with pytest.raises(ValueError):
        _base_inputs(base_revenue=-100)


def test_growth_list_length_mismatch():
    with pytest.raises(ValueError, match="revenue_growth"):
        _base_inputs(revenue_growth=[0.10, 0.10], projection_years=5)
