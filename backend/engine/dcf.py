"""Pure DCF math — no LLM. All amounts in millions USD; rates as decimals (0.10 = 10%)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

RateField = float | list[float]


def _normalize_rate(value: float) -> float:
    """Accept 10 or 0.10 for 10%; store as decimal."""
    if abs(value) > 1:
        return value / 100
    return value


def _normalize_rate_field(v: RateField) -> RateField:
    if isinstance(v, list):
        return [_normalize_rate(x) for x in v]
    return _normalize_rate(v)


class DcfInputs(BaseModel):
    base_revenue: float = Field(gt=0, description="Starting revenue in millions USD")
    revenue_growth: RateField = Field(
        description="Annual revenue growth as decimal(s), e.g. 0.10 for 10%"
    )
    ebitda_margin: RateField
    da_pct: RateField
    tax_rate: RateField
    capex_pct: RateField
    nwc_pct: RateField
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
    def _normalize_growth(cls, v: RateField) -> RateField:
        return _normalize_rate_field(v)

    @field_validator(
        "ebitda_margin",
        "da_pct",
        "tax_rate",
        "capex_pct",
        "nwc_pct",
        mode="before",
    )
    @classmethod
    def _normalize_rate_fields(cls, v: RateField) -> RateField:
        return _normalize_rate_field(v)

    @field_validator("wacc", "terminal_growth", mode="before")
    @classmethod
    def _normalize_scalar_rates(cls, v: float) -> float:
        return _normalize_rate(v)

    @model_validator(mode="after")
    def _validate_model(self) -> DcfInputs:
        if self.wacc <= self.terminal_growth:
            raise ValueError("WACC must be greater than terminal growth rate")
        n = self.projection_years
        for field in (
            "revenue_growth",
            "ebitda_margin",
            "da_pct",
            "tax_rate",
            "capex_pct",
            "nwc_pct",
        ):
            series = self._rate_series(getattr(self, field), n)
            if len(series) != n:
                raise ValueError(
                    f"{field} must be a single rate or a list of {n} rates"
                )
        return self

    def _rate_series(self, value: RateField, years: int | None = None) -> list[float]:
        n = years if years is not None else self.projection_years
        if isinstance(value, list):
            return value
        return [value] * n

    def _growth_rates(self) -> list[float]:
        return self._rate_series(self.revenue_growth)

    def margin_rates(self) -> list[float]:
        return self._rate_series(self.ebitda_margin)

    def tax_rates(self) -> list[float]:
        return self._rate_series(self.tax_rate)

    def da_rates(self) -> list[float]:
        return self._rate_series(self.da_pct)

    def capex_rates(self) -> list[float]:
        return self._rate_series(self.capex_pct)

    def nwc_rates(self) -> list[float]:
        return self._rate_series(self.nwc_pct)


class DcfYearRow(BaseModel):
    year: int
    revenue: float
    ebitda: float
    da: float
    ebit: float
    taxes: float
    capex: float
    nwc: float
    delta_nwc: float
    ufcf: float
    fcf: float
    terminal_value: float
    total_ufcf: float
    discount_factor: float
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
    margins = inputs.margin_rates()
    da_pcts = inputs.da_rates()
    taxes = inputs.tax_rates()
    capex_pcts = inputs.capex_rates()
    nwc_pcts = inputs.nwc_rates()
    wacc = inputs.wacc
    g = inputs.terminal_growth

    revenue = inputs.base_revenue
    years_raw: list[dict[str, float | int]] = []
    pv_fcf_sum = 0.0

    for t in range(1, inputs.projection_years + 1):
        idx = t - 1
        prev_revenue = revenue
        revenue = revenue * (1 + growths[idx])
        ebitda = revenue * margins[idx]
        da = revenue * da_pcts[idx]
        ebit = ebitda - da
        tax = ebit * taxes[idx]
        capex = revenue * capex_pcts[idx]
        nwc = revenue * nwc_pcts[idx]
        prev_nwc = prev_revenue * (nwc_pcts[idx - 1] if idx > 0 else nwc_pcts[0])
        delta_nwc = nwc - prev_nwc
        ufcf = ebitda - tax - capex - delta_nwc

        years_raw.append(
            {
                "year": t,
                "revenue": revenue,
                "ebitda": ebitda,
                "da": da,
                "ebit": ebit,
                "taxes": tax,
                "capex": capex,
                "nwc": nwc,
                "delta_nwc": delta_nwc,
                "ufcf": ufcf,
            }
        )

    final_ufcf = float(years_raw[-1]["ufcf"]) if years_raw else 0.0
    terminal_value = final_ufcf * (1 + g) / (wacc - g)
    pv_terminal = terminal_value / (1 + wacc) ** inputs.projection_years

    years: list[DcfYearRow] = []
    for row in years_raw:
        t = int(row["year"])
        is_last = t == inputs.projection_years
        terminal_in_year = terminal_value if is_last else 0.0
        total_ufcf = float(row["ufcf"]) + terminal_in_year
        discount_factor = (1 + wacc) ** t
        pv_fcf = total_ufcf / discount_factor
        pv_fcf_sum += pv_fcf

        years.append(
            DcfYearRow(
                year=t,
                revenue=round(float(row["revenue"]), 4),
                ebitda=round(float(row["ebitda"]), 4),
                da=round(float(row["da"]), 4),
                ebit=round(float(row["ebit"]), 4),
                taxes=round(float(row["taxes"]), 4),
                capex=round(float(row["capex"]), 4),
                nwc=round(float(row["nwc"]), 4),
                delta_nwc=round(float(row["delta_nwc"]), 4),
                ufcf=round(float(row["ufcf"]), 4),
                fcf=round(float(row["ufcf"]), 4),
                terminal_value=round(terminal_in_year, 4),
                total_ufcf=round(total_ufcf, 4),
                discount_factor=round(discount_factor, 6),
                pv_fcf=round(pv_fcf, 4),
            )
        )

    enterprise_value = pv_fcf_sum

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
