"""HTML report for HF normalization test runs."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def _fmt_usd(val: Any) -> str:
    if val is None:
        return "—"
    try:
        num = float(val)
    except (TypeError, ValueError):
        return html.escape(str(val))
    if abs(num) >= 1e9:
        return f"${num / 1e9:,.2f}B"
    if abs(num) >= 1e6:
        return f"${num / 1e6:,.2f}M"
    return f"${num:,.0f}"


def _status_badge(status: str) -> str:
    colors = {
        "ok": ("#dcfce7", "#166534"),
        "baseline_only": ("#e0e7ff", "#3730a3"),
        "hf_parse_error": ("#fef3c7", "#92400e"),
        "hf_error": ("#fee2e2", "#991b1b"),
        "error": ("#fee2e2", "#991b1b"),
    }
    bg, fg = colors.get(status, ("#f3f4f6", "#374151"))
    return (
        f'<span class="badge" style="background:{bg};color:{fg}">'
        f"{html.escape(status)}</span>"
    )


def _mapped_table(items: list[dict[str, Any]] | None) -> str:
    if not items:
        return '<p class="muted">No parsed mapping</p>'
    header = (
        "<tr><th>Tag</th><th>Standard concept</th><th>Label</th>"
        "<th>Concept</th><th>Value</th></tr>"
    )
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(item.get('tag', '')))}</td>"
            f"<td><strong>{html.escape(str(item.get('standard_concept', '')))}</strong></td>"
            f"<td>{html.escape(str(item.get('label', '')))}</td>"
            f"<td class='mono'>{html.escape(str(item.get('concept', '')))}</td>"
            f"<td class='num'>{_fmt_usd(item.get('value'))}</td>"
            "</tr>"
        )
    return f"<table class='data-table'><thead>{header}</thead><tbody>{''.join(rows)}</tbody></table>"


def _line_items_table(items: list[dict[str, Any]] | None, *, limit: int = 40) -> str:
    if not items:
        return '<p class="muted">No line items</p>'
    shown = items[:limit]
    extra = len(items) - len(shown)
    header = "<tr><th>Label</th><th>Concept</th><th>Value</th></tr>"
    rows = []
    for item in shown:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(item.get('label', '')))}</td>"
            f"<td class='mono'>{html.escape(str(item.get('concept', '')))}</td>"
            f"<td class='num'>{_fmt_usd(item.get('value'))}</td>"
            "</tr>"
        )
    tail = f"<p class='muted'>+ {extra} more rows in baseline.json</p>" if extra > 0 else ""
    return (
        f"<table class='data-table compact'><thead>{header}</thead>"
        f"<tbody>{''.join(rows)}</tbody></table>{tail}"
    )


def build_report_html(
    *,
    manifest: dict[str, Any],
    output_dir: Path,
) -> str:
    results = manifest.get("results", [])
    ok = sum(1 for r in results if r.get("status") == "ok")
    fetch_only = manifest.get("fetch_only", False)

    summary_rows = []
    company_sections = []

    for entry in results:
        ticker = entry.get("ticker", "?")
        status = entry.get("status", "unknown")
        ticker_dir = output_dir / ticker
        baseline_path = ticker_dir / "baseline.json"
        hf_path = ticker_dir / "hf_response.json"
        mapped_path = ticker_dir / "hf_mapped.json"

        baseline = {}
        if baseline_path.exists():
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

        hf_mapped: list[dict[str, Any]] | None = None
        parse_error = entry.get("parse_error") or entry.get("error", "")
        if mapped_path.exists():
            hf_mapped = json.loads(mapped_path.read_text(encoding="utf-8"))
        elif hf_path.exists():
            hf_data = json.loads(hf_path.read_text(encoding="utf-8"))
            hf_mapped = hf_data.get("parsed_array")
            parse_error = parse_error or hf_data.get("parse_error", "")

        rev_hf = next(
            (m.get("value") for m in (hf_mapped or []) if m.get("standard_concept") == "Revenue"),
            None,
        )
        rev_edgar = baseline.get("smart_revenue_usd")

        summary_rows.append(
            "<tr>"
            f"<td><a href='#co-{ticker}'>{html.escape(ticker)}</a></td>"
            f"<td>{html.escape(str(baseline.get('entity_name', '')))}</td>"
            f"<td>{_status_badge(status)}</td>"
            f"<td>FY{html.escape(str(baseline.get('fiscal_year', '')))}</td>"
            f"<td class='num'>{_fmt_usd(rev_edgar)}</td>"
            f"<td class='num'>{_fmt_usd(rev_hf)}</td>"
            f"<td class='mono'>{html.escape(str(baseline.get('smart_revenue_tag') or ''))}</td>"
            "</tr>"
        )

        err_block = ""
        if parse_error:
            err_block = f'<p class="warn">{html.escape(str(parse_error))}</p>'

        company_sections.append(
            f"""
<section class="card company" id="co-{html.escape(ticker)}">
  <h2>{html.escape(ticker)} — {html.escape(str(baseline.get('entity_name', '')))}
      {_status_badge(status)}</h2>
  <p class="meta">FY{baseline.get('fiscal_year')} · period {html.escape(str(baseline.get('period_end', '')))}
     · edgartools smart_revenue ref: {_fmt_usd(rev_edgar)} ({html.escape(str(baseline.get('smart_revenue_tag') or '—'))})</p>
  {err_block}
  <h3>HF mapped buckets</h3>
  {_mapped_table(hf_mapped)}
  <details>
    <summary>Input line items sent to model ({len(baseline.get('line_items') or [])} rows)</summary>
    {_line_items_table(baseline.get('line_items'))}
  </details>
</section>
"""
        )

    mode = "fetch-only (no HF calls)" if fetch_only else f"model: {html.escape(str(manifest.get('model_id', '')))}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>HF normalization test — {html.escape(str(manifest.get('run_id', '')))}</title>
  <style>
    :root {{ --border: #e5e7ef; --muted: #6b7280; --bg: #f8f9fc; }}
    body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 0; background: var(--bg); color: #111827; }}
    header {{ background: linear-gradient(135deg,#fff,#eef2ff); border-bottom: 1px solid var(--border); padding: 1.25rem 1.5rem; }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 1rem 1.5rem 2rem; }}
    h1 {{ margin: 0 0 .25rem; font-size: 1.35rem; }}
    .meta {{ color: var(--muted); font-size: .875rem; }}
    .card {{ background: #fff; border: 1px solid var(--border); border-radius: 12px; padding: 1rem; margin-bottom: 1rem; }}
    .company h2 {{ margin: 0 0 .5rem; font-size: 1.1rem; display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; }}
    .company h3 {{ font-size: .95rem; margin: 1rem 0 .5rem; }}
    .badge {{ font-size: .7rem; padding: .15rem .45rem; border-radius: 999px; font-weight: 600; }}
    .data-table {{ width: 100%; border-collapse: collapse; font-size: .8rem; }}
    .data-table th {{ text-align: left; background: #f3f4f6; padding: .45rem .5rem; border-bottom: 1px solid var(--border); }}
    .data-table td {{ padding: .35rem .5rem; border-bottom: 1px solid #f0f0f5; vertical-align: top; }}
    .data-table.compact td, .data-table.compact th {{ font-size: .75rem; }}
    .num {{ font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }}
    .mono {{ font-family: ui-monospace, monospace; font-size: .72rem; word-break: break-all; }}
    .muted {{ color: var(--muted); font-style: italic; }}
    .warn {{ color: #b45309; background: #fffbeb; border: 1px solid #fde68a; padding: .5rem .75rem; border-radius: 8px; }}
    details {{ margin-top: .75rem; }}
    summary {{ cursor: pointer; color: #4338ca; font-size: .85rem; }}
    .table-wrap {{ overflow: auto; }}
  </style>
</head>
<body>
  <header>
    <h1>HF income statement normalization — review</h1>
    <p class="meta">Run {html.escape(str(manifest.get('run_id', '')))} · {mode} ·
       {ok}/{len(results)} HF ok · {html.escape(str(manifest.get('started_at', '')))}</p>
  </header>
  <main>
    <div class="card">
      <h2 style="margin:0 0 .75rem;font-size:1rem;">Summary — Revenue comparison</h2>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Ticker</th><th>Company</th><th>Status</th><th>FY</th>
              <th>Edgartools smart_revenue</th><th>HF Revenue bucket</th><th>Edgar tag</th>
            </tr>
          </thead>
          <tbody>{''.join(summary_rows)}</tbody>
        </table>
      </div>
      <p class="meta" style="margin-top:.75rem;">Fill manual verification in review_sheet.csv.
         Open each company section below for full HF bucket mapping.</p>
    </div>
    {''.join(company_sections)}
  </main>
</body>
</html>"""


def write_report_html(*, manifest: dict[str, Any], output_dir: Path) -> Path:
    path = output_dir / "report.html"
    path.write_text(
        build_report_html(manifest=manifest, output_dir=output_dir),
        encoding="utf-8",
    )
    return path
