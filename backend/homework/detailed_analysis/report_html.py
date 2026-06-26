"""Self-contained HTML report for detailed analysis homework."""

from __future__ import annotations

import html
from typing import Any

from ingest.detailed_disclaimer import (
    BANK_SECTOR_DISCLAIMER,
    DETAILED_ANALYSIS_DISCLAIMER,
    FCF_FOOTNOTE,
    NET_CASH_TOOLTIP,
)
from ingest.detailed_extract import (
    BALANCE_GROUP_LABELS,
    DETAILED_BALANCE_ORDER,
    DETAILED_CASHFLOW_ORDER,
    DETAILED_INCOME_ORDER,
    DETAILED_LABELS,
    DetailedAnalysisSnapshot,
    MetricCell,
)


def _fmt_value(val: float | None) -> str:
    if val is None:
        return "n/a"
    num = float(val)
    if abs(num) >= 1e9:
        return f"${num / 1e9:,.2f}B"
    if abs(num) >= 1e6:
        return f"${num / 1e6:,.1f}M"
    return f"${num:,.0f}"


def _cell_title(cell: MetricCell) -> str:
    parts = []
    if cell.xbrl_tag:
        parts.append(f"tag: {cell.xbrl_tag}")
    if cell.label:
        parts.append(f"row: {cell.label}")
    if cell.source_statement:
        parts.append(f"from: {cell.source_statement}")
    if cell.source == "derived":
        parts.append("derived")
    if cell.warning:
        parts.append(f"⚠ {cell.warning}")
    return " | ".join(parts)


def _row_cells(cells: list[MetricCell], *, na_muted: bool = False) -> str:
    tds = []
    for cell in cells:
        css = "num"
        if cell.value is None or cell.source == "n/a":
            css += " muted"
        title = html.escape(_cell_title(cell))
        tds.append(
            f'<td class="{css}" title="{title}">{html.escape(_fmt_value(cell.value))}</td>'
        )
    return "".join(tds)


def _comparison_table(
    keys: tuple[str, ...],
    periods: list,
    *,
    get_cells: Any,
    group_labels: dict[str, str] | None = None,
) -> str:
    if not periods:
        return '<p class="empty">No periods</p>'

    headers = "".join(
        f"<th>FY{p.fiscal_year}</th>" for p in periods
    )
    rows: list[str] = []
    last_group: str | None = None
    for key in keys:
        group = (group_labels or {}).get(key)
        if group and group != last_group:
            rows.append(
                f'<tr class="group-row"><td colspan="{len(periods) + 1}">'
                f"{html.escape(group)}</td></tr>"
            )
            last_group = group
        cells = [get_cells(p, key) for p in periods]
        label = DETAILED_LABELS.get(key, key)
        rows.append(
            f"<tr><td class=\"label\">{html.escape(label)}</td>{_row_cells(cells)}</tr>"
        )
    return f"""
    <table class="compare-table">
      <thead><tr><th>Line item</th>{headers}</tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
    """


def _accounting_equation_footer(periods: list) -> str:
    if not periods:
        return ""
    badges: list[str] = []
    for p in periods:
        assets = p.balance.get("total_assets")
        liab = p.balance.get("total_liabilities")
        equity = p.balance.get("stockholders_equity")
        ok = p.accounting_equation_ok
        if ok is True:
            css = "eq-ok"
            text = "✓"
        elif ok is False:
            css = "eq-warn"
            text = "⚠ mismatch"
        else:
            css = "eq-na"
            text = "n/a"
        badges.append(
            f'<span class="eq-badge {css}">FY{p.fiscal_year} {text}</span>'
        )
    return (
        f'<div class="eq-check"><strong>A = L + E check:</strong> {"".join(badges)}</div>'
    )


def build_report_html(snapshot: DetailedAnalysisSnapshot) -> str:
    periods = snapshot.periods
    warnings_html = ""
    if snapshot.warnings:
        items = "".join(f"<li>{html.escape(w)}</li>" for w in snapshot.warnings)
        warnings_html = f'<ul class="warnings">{items}</ul>'

    integrity_html = ""
    if snapshot.integrity_checks:
        items = "".join(f"<li>{html.escape(n)}</li>" for n in snapshot.integrity_checks)
        integrity_html = f"""
        <div class="card integrity">
          <h2>Integrity checks</h2>
          <ul class="checks">{items}</ul>
        </div>
        """

    income_table = _comparison_table(
        DETAILED_INCOME_ORDER,
        periods,
        get_cells=lambda p, k: p.income.get(k, MetricCell(key=k)),
    )
    balance_table = _comparison_table(
        DETAILED_BALANCE_ORDER,
        periods,
        get_cells=lambda p, k: p.balance.get(k, MetricCell(key=k)),
        group_labels=BALANCE_GROUP_LABELS,
    )
    cashflow_table = _comparison_table(
        DETAILED_CASHFLOW_ORDER,
        periods,
        get_cells=lambda p, k: p.cashflow.get(k, MetricCell(key=k)),
    )

    bank_banner = ""
    if snapshot.is_bank_style:
        bank_banner = (
            f'<p class="bank-banner">{html.escape(BANK_SECTOR_DISCLAIMER)}</p>'
        )

    eq_footer = _accounting_equation_footer(periods)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(snapshot.ticker)} — Detailed Analysis</title>
  <style>
    :root {{
      --bg: #f4f6fb;
      --card: #fff;
      --border: #e2e8f0;
      --accent: #4f46e5;
      --text: #1e293b;
      --muted: #94a3b8;
      --warn: #b45309;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
    }}
    header {{
      background: linear-gradient(135deg, #fff 0%, #eef2ff 100%);
      border-bottom: 1px solid var(--border);
      padding: 1.25rem 1.5rem;
    }}
    header h1 {{ margin: 0 0 0.25rem; font-size: 1.35rem; }}
    header .meta {{ color: #64748b; font-size: 0.875rem; }}
    main {{ padding: 1rem 1.5rem 2rem; max-width: 1200px; margin: 0 auto; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
      margin-bottom: 1rem;
    }}
    .warnings {{ color: var(--warn); margin: 0.5rem 0 0; padding-left: 1.25rem; }}
    .checks {{ color: var(--warn); margin: 0; padding-left: 1.25rem; font-size: 0.875rem; }}
    .tabs {{ display: flex; gap: 0.35rem; margin-bottom: 0.75rem; }}
    .tab-btn {{
      border: 1px solid var(--border);
      background: #f8fafc;
      border-radius: 8px;
      padding: 0.45rem 0.9rem;
      cursor: pointer;
      font-size: 0.875rem;
    }}
    .tab-btn.active {{
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }}
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}
    .compare-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.875rem;
    }}
    .compare-table th, .compare-table td {{
      border-bottom: 1px solid var(--border);
      padding: 0.5rem 0.65rem;
      text-align: right;
    }}
    .compare-table th:first-child, .compare-table td.label {{
      text-align: left;
      font-weight: 500;
    }}
    .compare-table .num {{ font-variant-numeric: tabular-nums; }}
    .compare-table .muted {{ color: var(--muted); }}
    .group-row td {{
      background: #f1f5f9;
      font-weight: 600;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: #475569;
      text-align: left !important;
    }}
    .empty {{ color: var(--muted); }}
    .hint {{ font-size: 0.8rem; color: #64748b; margin-top: 0.5rem; }}
    .disclaimer {{
      background: #fffbeb;
      border-bottom: 1px solid #fde68a;
      padding: 0.85rem 1.5rem;
      font-size: 0.8rem;
      color: #78350f;
      line-height: 1.5;
    }}
    .bank-banner {{
      margin: 0.5rem 0 0;
      font-weight: 600;
      color: #92400e;
    }}
    .eq-check {{
      margin-top: 0.75rem;
      padding-top: 0.75rem;
      border-top: 1px solid var(--border);
      font-size: 0.8rem;
      color: #64748b;
    }}
    .eq-badge {{ margin-right: 0.75rem; }}
    .eq-ok {{ color: #047857; }}
    .eq-warn {{ color: var(--warn); }}
    .eq-na {{ color: var(--muted); }}
    .footnote {{ font-size: 0.8rem; color: #64748b; margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid var(--border); }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(snapshot.ticker)} — Detailed Analysis</h1>
    <div class="meta">
      {html.escape(snapshot.entity_name)} · CIK {html.escape(snapshot.cik)} ·
      {html.escape(snapshot.fetched_at)} · source: {html.escape(snapshot.source)}
    </div>
    {warnings_html}
  </header>
  <div class="disclaimer">
    <p>{html.escape(DETAILED_ANALYSIS_DISCLAIMER)}</p>
    {bank_banner}
  </div>
  <main>
    {integrity_html}
    <div class="card">
      <div class="tabs" role="tablist">
        <button type="button" class="tab-btn active" data-tab="income">Income Statement</button>
        <button type="button" class="tab-btn" data-tab="balance">Balance Sheet</button>
        <button type="button" class="tab-btn" data-tab="cashflow">Cash Flow</button>
      </div>
      <section class="tab-panel active" id="panel-income" data-tab="income">
        {income_table}
      </section>
      <section class="tab-panel" id="panel-balance" data-tab="balance">
        {balance_table}
        {eq_footer}
      </section>
      <section class="tab-panel" id="panel-cashflow" data-tab="cashflow">
        {cashflow_table}
        <p class="footnote">{html.escape(FCF_FOOTNOTE)}</p>
        <p class="footnote">{html.escape(NET_CASH_TOOLTIP)}</p>
      </section>
      <p class="hint">Hover a value for XBRL tag, filed row label, and warnings.</p>
    </div>
  </main>
  <script>
    document.querySelectorAll('.tab-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        const tab = btn.dataset.tab;
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.dataset.tab === tab));
      }});
    }});
  </script>
</body>
</html>
"""


def build_validation_md(snapshot: DetailedAnalysisSnapshot) -> str:
    lines = [
        f"# Validation — {snapshot.ticker}",
        "",
        f"Entity: {snapshot.entity_name}",
        f"Fetched: {snapshot.fetched_at}",
        f"Source: {snapshot.source}",
        "",
        "## Integrity checks",
        "",
    ]
    if snapshot.integrity_checks:
        lines.extend(f"- {n}" for n in snapshot.integrity_checks)
    else:
        lines.append("- All checks passed (or no data to compare).")
    lines.extend(["", "## Warnings", ""])
    if snapshot.warnings:
        lines.extend(f"- {w}" for w in snapshot.warnings)
    else:
        lines.append("- None")
    lines.extend(["", "## Periods", ""])
    for p in snapshot.periods:
        lines.append(f"- FY{p.fiscal_year} ({p.period_end})")
    return "\n".join(lines) + "\n"
