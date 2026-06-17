"""Pure DCF math — no LLM. All amounts in millions USD; rates as decimals (0.10 = 10%)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


def _normalize_rate(value: float) -> float:
    """Accept 10 or 0.10 for 10%; store as decimal."""
    if abs(value) > 1:
        return value / 100
    return value


class DcfInputs(BaseModel):
    base_revenue: float = Field(gt=0, description="Starting revenue in millions USD")
    revenue_growth: float | list[float] = Field(
        description="Annual revenue growth as decimal(s), e.g. 0.10 for 10%"
    )
    ebitda_margin: float
    tax_rate: float
    capex_pct: float
    nwc_pct: float
    wacc: float
    terminal_growth: float
    projection_years: int = Field(ge=1, le=10)
    net_debt: float | None = Field(
        default=None, description="Debt minus cash, millions USD"
    )
    shares_outstanding: float | None = Field(
        default=None, gt=0, description="Shares in millions"
    )

    @field_validator("revenue_growth", mode="before")
    @classmethod
    def _normalize_growth(cls, v: float | list[float]) -> float | list[float]:
        if isinstance(v, list):
            return [_normalize_rate(x) for x in v]
        return _normalize_rate(v)

    @field_validator(
        "ebitda_margin",
        "tax_rate",
        "capex_pct",
        "nwc_pct",
        "wacc",
        "terminal_growth",
        mode="before",
    )
    @classmethod
    def _normalize_rates(cls, v: float) -> float:
        return _normalize_rate(v)

    @model_validator(mode="after")
    def _validate_model(self) -> DcfInputs:
        if self.wacc <= self.terminal_growth:
            raise ValueError("WACC must be greater than terminal growth rate")
        growths = self._growth_rates()
        if len(growths) != self.projection_years:
            raise ValueError(
                f"revenue_growth must be a single rate or a list of "
                f"{self.projection_years} rates"
            )
        return self

    def _growth_rates(self) -> list[float]:
        if isinstance(self.revenue_growth, list):
            return self.revenue_growth
        return [self.revenue_growth] * self.projection_years


class DcfYearRow(BaseModel):
    year: int
    revenue: float
    ebitda: float
    fcf: float
    pv_fcf: float


class DcfResult(BaseModel):
    inputs: DcfInputs
    years: list[DcfYearRow]
    terminal_value: float
    pv_terminal: float
    enterprise_value: float
    equity_value: float | None = None
    price_per_share: float | None = None
    company_name: str | None = None


def compute_dcf(inputs: DcfInputs, company_name: str | None = None) -> DcfResult:
    growths = inputs._growth_rates()
    wacc = inputs.wacc
    g = inputs.terminal_growth

    revenue = inputs.base_revenue
    years: list[DcfYearRow] = []
    pv_fcf_sum = 0.0
    final_fcf = 0.0

    for t in range(1, inputs.projection_years + 1):
        revenue = revenue * (1 + growths[t - 1])
        prev_revenue = revenue / (1 + growths[t - 1])
        ebitda = revenue * inputs.ebitda_margin
        nopat = ebitda * (1 - inputs.tax_rate)
        capex = revenue * inputs.capex_pct
        delta_nwc = (revenue - prev_revenue) * inputs.nwc_pct
        fcf = nopat - capex - delta_nwc
        pv_fcf = fcf / (1 + wacc) ** t
        pv_fcf_sum += pv_fcf
        final_fcf = fcf

        years.append(
            DcfYearRow(
                year=t,
                revenue=round(revenue, 4),
                ebitda=round(ebitda, 4),
                fcf=round(fcf, 4),
                pv_fcf=round(pv_fcf, 4),
            )
        )

    terminal_value = final_fcf * (1 + g) / (wacc - g)
    pv_terminal = terminal_value / (1 + wacc) ** inputs.projection_years
    enterprise_value = pv_fcf_sum + pv_terminal

    equity_value: float | None = None
    price_per_share: float | None = None
    if inputs.net_debt is not None:
        equity_value = enterprise_value - inputs.net_debt
        if inputs.shares_outstanding is not None:
            price_per_share = equity_value / inputs.shares_outstanding

    return DcfResult(
        inputs=inputs,
        years=years,
        terminal_value=round(terminal_value, 4),
        pv_terminal=round(pv_terminal, 4),
        enterprise_value=round(enterprise_value, 4),
        equity_value=round(equity_value, 4) if equity_value is not None else None,
        price_per_share=round(price_per_share, 4) if price_per_share is not None else None,
        company_name=company_name,
    )
