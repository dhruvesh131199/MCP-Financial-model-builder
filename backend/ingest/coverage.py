"""Build per-metric coverage reports for normalized financial statements."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from ingest.metric_catalog import METRICS_BY_KEY, STATEMENT_METRIC_ORDER, MetricDef

CoverageStatus = Literal["present", "derived", "missing", "not_applicable"]


class CoverageEntry(BaseModel):
    key: str
    label: str
    status: CoverageStatus
    value: float | None = None
    reason: str | None = None
    xbrl_tag: str | None = None
    derived_from: list[str] | None = None
    statement: str | None = None


def _line_item_map(period: dict) -> dict[str, dict]:
    return {li["key"]: li for li in period.get("line_items") or []}


def _period_for_year(financials: dict, fiscal_year: int) -> dict[str, dict[str, dict]]:
    """statement -> line_key -> line_item for one fiscal year (annual FY)."""
    out: dict[str, dict[str, dict]] = {}
    for stmt_key, slice_ in (financials.get("statements") or {}).items():
        for period in slice_.get("annual") or []:
            if int(period.get("fiscal_year", 0)) == fiscal_year and period.get("fiscal_period") == "FY":
                out[stmt_key] = _line_item_map(period)
                break
    return out


def _ever_reported(financials: dict, key: str) -> bool:
    for slice_ in (financials.get("statements") or {}).values():
        for period in (slice_.get("annual") or []) + (slice_.get("quarterly") or []):
            if any(li.get("key") == key for li in period.get("line_items") or []):
                return True
    return False


def _status_for_metric(
    metric: MetricDef,
    line_item: dict | None,
    financials: dict,
) -> tuple[CoverageStatus, str | None]:
    if line_item is not None:
        source = line_item.get("source", "xbrl")
        if source == "derived":
            parts = line_item.get("derived_from") or []
            return "derived", f"Calculated from: {', '.join(parts)}"
        tag = line_item.get("xbrl_tag")
        ns = "dei" if tag == "EntityCommonStockSharesOutstanding" else "us-gaap"
        return "present", f"Mapped from {ns}:{tag}" if tag else "Mapped from SEC XBRL"

    if metric.key == "gross_profit" and not _ever_reported(financials, "cost_of_revenue"):
        return (
            "not_applicable",
            "Filer does not report cost of revenue (common for asset-light / platform businesses)",
        )
    if metric.key == "cost_of_revenue" and not _ever_reported(financials, "cost_of_revenue"):
        return (
            "not_applicable",
            "Not reported in SEC XBRL for this filer",
        )

    if metric.applicability == "industry_optional" and not _ever_reported(financials, metric.key):
        return "not_applicable", f"Not reported in SEC XBRL for this filer"

    if metric.key in ("ebitda", "free_cash_flow"):
        return "missing", "Could not derive — missing required components"

    return "missing", "Not found in SEC XBRL (tried all known tag aliases)"


def build_coverage_report(
    financials: dict,
    fiscal_year: int,
) -> dict[str, CoverageEntry]:
    """Coverage for all canonical metrics for one fiscal year."""
    period_maps = _period_for_year(financials, fiscal_year)
    report: dict[str, CoverageEntry] = {}

    for stmt_key, order in STATEMENT_METRIC_ORDER.items():
        lines = period_maps.get(stmt_key, {})
        for key in order:
            metric = METRICS_BY_KEY.get(key)
            if not metric:
                continue
            li = lines.get(key)
            status, reason = _status_for_metric(metric, li, financials)
            report[key] = CoverageEntry(
                key=key,
                label=metric.label,
                status=status,
                value=float(li["value"]) if li else None,
                reason=reason,
                xbrl_tag=li.get("xbrl_tag") if li else None,
                derived_from=li.get("derived_from") if li else None,
                statement=stmt_key,
            )

    return report


def build_comps_field_status(
    snapshot: dict[str, Any],
    coverage: dict[str, CoverageEntry] | None,
    *,
    market_ok: bool = True,
    market_errors: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Explain null comparative fields using coverage + market data context."""
    field_status: dict[str, dict[str, Any]] = {}

    def _set(field: str, value: Any, reason: str | None, status: str = "present") -> None:
        if value is not None:
            field_status[field] = {"status": status, "value": value, "reason": reason}
        else:
            field_status[field] = {"status": "missing", "value": None, "reason": reason}

    cov = coverage or {}

    def _cov_status(entry: Any) -> str | None:
        if entry is None:
            return None
        if isinstance(entry, dict):
            return entry.get("status")
        return getattr(entry, "status", None)

    def _cov_reason(entry: Any) -> str | None:
        if entry is None:
            return None
        if isinstance(entry, dict):
            return entry.get("reason")
        return getattr(entry, "reason", None)

    gross_margin = snapshot.get("gross_margin")
    if gross_margin is None:
        gp_cov = cov.get("gross_profit") or cov.get("cost_of_revenue")
        if gp_cov and _cov_status(gp_cov) == "not_applicable":
            field_status["gross_margin"] = {
                "status": "not_applicable",
                "value": None,
                "reason": _cov_reason(gp_cov),
            }
        else:
            field_status["gross_margin"] = {
                "status": "missing",
                "value": None,
                "reason": "Gross profit or revenue not available",
            }
    else:
        _set("gross_margin", gross_margin, "Gross profit ÷ revenue")

    ratio_fields = {
        "operating_margin": "Operating income ÷ revenue",
        "net_margin": "Net income ÷ revenue",
        "roe": "Net income ÷ stockholders' equity",
        "roa": "Net income ÷ total assets",
        "fcf_margin": "Free cash flow ÷ revenue",
        "book_value_per_share": "Stockholders' equity ÷ shares outstanding",
        "revenue_growth_yoy": "YoY revenue change",
        "net_income_growth_yoy": "YoY net income change",
    }
    for field, desc in ratio_fields.items():
        val = snapshot.get(field)
        if val is not None:
            _set(field, val, desc)
        else:
            deps = {
                "operating_margin": ("operating_income", "revenue"),
                "net_margin": ("net_income", "revenue"),
                "roe": ("net_income", "stockholders_equity"),
                "roa": ("net_income", "total_assets"),
                "fcf_margin": ("free_cash_flow", "revenue"),
                "book_value_per_share": ("stockholders_equity", "shares_outstanding"),
            }
            if field in deps:
                a, b = deps[field]
                missing = [k for k in (a, b) if snapshot.get(k) is None]
                field_status[field] = {
                    "status": "missing",
                    "value": None,
                    "reason": f"Missing: {', '.join(missing)}" if missing else desc,
                }
            else:
                field_status[field] = {
                    "status": "missing",
                    "value": None,
                    "reason": "Prior-year comparison not available",
                }

    for key in (
        "revenue",
        "net_income",
        "total_assets",
        "stockholders_equity",
        "ebitda",
        "eps_diluted",
        "shares_outstanding",
        "free_cash_flow",
        "net_debt",
    ):
        val = snapshot.get(key)
        if val is not None:
            c = cov.get(key)
            st = _cov_status(c) if c else "present"
            field_status[key] = {
                "status": st or "present",
                "value": val,
                "reason": _cov_reason(c) if c else None,
            }
        elif key in cov:
            c = cov[key]
            field_status[key] = {
                "status": _cov_status(c) or "missing",
                "value": None,
                "reason": _cov_reason(c),
            }
        else:
            field_status[key] = {
                "status": "missing",
                "value": None,
                "reason": "Not available",
            }

    if not market_ok:
        err_msg = "; ".join(market_errors or []) or "Finnhub market data unavailable"
        for mfield in (
            "pe_ratio",
            "pb_ratio",
            "ev_to_sales",
            "ev_to_ebitda",
            "stock_price",
            "market_cap_usd",
        ):
            field_status[mfield] = {
                "status": "missing",
                "value": None,
                "reason": err_msg,
            }

    return field_status
