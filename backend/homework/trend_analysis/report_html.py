"""HTML snippet for trend analysis homework review."""

from __future__ import annotations

from engine.trend_analysis import TrendAnalysisTable


def _fmt_value(row_type: str, value: float | None) -> str:
    if value is None:
        return "—"
    if row_type == "currency":
        abs_v = abs(value)
        if abs_v >= 1e9:
            return f"${value / 1e9:.2f}B"
        if abs_v >= 1e6:
            return f"${value / 1e6:.1f}M"
        return f"${value:,.0f}"
    if row_type == "eps":
        return f"${value:.2f}"
    return f"{value:.1f}%"


def build_trend_html(table: TrendAnalysisTable) -> str:
    headers = "".join(f"<th>FY{y}</th>" for y in table.fiscal_years)
    body_rows = []
    for row in table.rows:
        cls = ' class="highlight"' if row.highlight else ""
        cells = "".join(
            f"<td>{_fmt_value(row.row_type, v)}</td>" for v in row.values
        )
        body_rows.append(f"<tr{cls}><td>{row.label}</td>{cells}</tr>")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Trend analysis</title>
  <style>
    body {{ font-family: system-ui, sans-serif; padding: 1.5rem; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 56rem; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 0.5rem 0.75rem; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    tr.highlight td {{ font-weight: 600; background: #f8fafc; }}
    h1 {{ font-size: 1.125rem; margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <h1>Trend analysis</h1>
  <table>
    <thead><tr><th>Line item</th>{headers}</tr></thead>
    <tbody>{"".join(body_rows)}</tbody>
  </table>
</body>
</html>
"""
