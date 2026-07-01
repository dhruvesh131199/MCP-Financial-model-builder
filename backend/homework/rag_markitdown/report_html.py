"""HTML viewer for homework ingest — section outline + metadata (no markdown dump)."""

from __future__ import annotations

import html

from homework.rag_markitdown.schema import IngestResult, ItemSection, SectionOutline


def _esc(text: str) -> str:
    return html.escape(text)


def _fmt_num(n: int) -> str:
    return f"{n:,}"


def _outline_row(label: str, chars: int, tokens: int) -> str:
    return (
        f"<tr class=\"item\">"
        f"<td>{_esc(label)}</td>"
        f"<td class=\"num\">{_fmt_num(chars)}</td>"
        f"<td class=\"num\">{_fmt_num(tokens)}</td>"
        f"</tr>"
    )


def _item_rows(section: ItemSection) -> str:
    return _outline_row(section.label, section.char_count, section.approx_tokens)


def _build_outline_table(outline: SectionOutline) -> str:
    rows = ""
    if outline.preamble:
        rows += _item_rows(outline.preamble)
    for item in outline.items:
        rows += _item_rows(item)
    if not rows:
        rows = (
            "<tr><td colspan=\"3\" class=\"empty\">No sections detected</td></tr>"
        )
    return rows


def build_report_html(
    result: IngestResult,
    markdown: str,
    outline: SectionOutline,
) -> str:
    del markdown
    filing = result.filing
    filing_rows = ""
    if filing:
        for label, val in (
            ("Ticker", filing.ticker),
            ("Entity", filing.entity_name),
            ("Form", filing.form),
            ("Accession", filing.accession_no),
            ("Filing date", filing.filing_date),
            ("Period end", filing.period_of_report),
            ("Primary doc", filing.primary_document),
        ):
            if val:
                filing_rows += (
                    f"<tr><th>{_esc(label)}</th><td>{_esc(str(val))}</td></tr>"
                )

    checks = "".join(
        f"<li class=\"{'ok' if ok else 'miss'}\">{_esc(k.replace('_', ' '))}: "
        f"{'found' if ok else 'not found'}</li>"
        for k, ok in result.narrative_checks.items()
    )

    warnings = ""
    if outline.warnings:
        warnings = (
            "<ul class=\"warnings\">"
            + "".join(f"<li>{_esc(w)}</li>" for w in outline.warnings)
            + "</ul>"
        )

    raw_href = _esc(result.raw_filename)
    ticker_label = (
        filing.ticker if filing and filing.ticker else result.document_id
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>RAG homework — {_esc(ticker_label)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }}
    header {{ background: linear-gradient(135deg, #4f46e5, #7c3aed); color: white; padding: 1.25rem 1.5rem; }}
    header h1 {{ margin: 0; font-size: 1.25rem; }}
    header p {{ margin: 0.35rem 0 0; opacity: 0.9; font-size: 0.9rem; }}
    .layout {{ display: grid; grid-template-columns: 280px 1fr; gap: 0; min-height: calc(100vh - 5rem); }}
    @media (max-width: 900px) {{ .layout {{ grid-template-columns: 1fr; }} }}
    .sidebar {{ padding: 1rem 1.25rem; border-right: 1px solid #e2e8f0; background: white; }}
    .main {{ padding: 1rem 1.25rem; background: white; }}
    h2 {{ font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin: 0 0 0.75rem; }}
    table.meta {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    table.meta th {{ text-align: left; color: #64748b; padding: 0.35rem 0.5rem 0.35rem 0; vertical-align: top; width: 38%; }}
    table.meta td {{ padding: 0.35rem 0; }}
    ul.checks {{ list-style: none; padding: 0; margin: 0.75rem 0; font-size: 0.85rem; }}
    ul.checks li {{ padding: 0.25rem 0; }}
    ul.checks li.ok {{ color: #047857; }}
    ul.checks li.miss {{ color: #b45309; }}
    ul.warnings {{ margin: 0.5rem 0 0; padding-left: 1.1rem; font-size: 0.8rem; color: #b45309; }}
    .actions {{ margin-bottom: 1rem; }}
    .btn {{
      display: inline-block; background: #4f46e5; color: white; text-decoration: none;
      padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.85rem; font-weight: 600;
    }}
    .btn:hover {{ background: #4338ca; }}
    table.outline {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    table.outline th {{
      text-align: left; padding: 0.5rem 0.75rem; border-bottom: 2px solid #e2e8f0;
      color: #64748b; font-weight: 600;
    }}
    table.outline td {{ padding: 0.45rem 0.75rem; border-bottom: 1px solid #f1f5f9; }}
    table.outline td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    table.outline tr.item td:first-child {{ font-weight: 600; }}
    table.outline tr.sub td:first-child {{ padding-left: 2rem; color: #475569; }}
    table.outline tr.empty td {{ color: #94a3b8; font-style: italic; }}
    .badge {{ display: inline-block; background: #e0e7ff; color: #3730a3; padding: 0.15rem 0.5rem;
      border-radius: 999px; font-size: 0.75rem; font-weight: 600; }}
    .footer-note {{ margin-top: 1rem; font-size: 0.78rem; color: #64748b; }}
  </style>
</head>
<body>
  <header>
    <h1>Annual report → section outline (homework)</h1>
    <p>Source: <span class="badge">{_esc(result.source.value)}</span>
       Format: <span class="badge">{_esc(result.source_format.value)}</span>
       · {_esc(f"{result.markdown_chars:,}")} chars
       · {outline.items_found} Item section(s)</p>
  </header>
  <div class="layout">
    <aside class="sidebar">
      <h2>Filing / ingest metadata</h2>
      <table class="meta">
        <tr><th>Document ID</th><td><code>{_esc(result.document_id)}</code></td></tr>
        <tr><th>Raw file</th><td>{_esc(result.raw_filename)} ({result.raw_bytes:,} bytes)</td></tr>
        {filing_rows}
      </table>
      <h2 style="margin-top:1.25rem">Narrative section checks</h2>
      <ul class="checks">{checks}</ul>
    </aside>
    <main class="main">
      <div class="actions">
        <a class="btn" href="{raw_href}" target="_blank" rel="noopener">Open original filing</a>
      </div>
      <h2>Section outline (chunk planning)</h2>
      {warnings}
      <table class="outline">
        <thead>
          <tr>
            <th>Section</th>
            <th style="text-align:right">Characters</th>
            <th style="text-align:right">~Tokens</th>
          </tr>
        </thead>
        <tbody>
          {_build_outline_table(outline)}
        </tbody>
      </table>
      <p class="footer-note">
        ~Tokens ≈ characters ÷ 4 (homework approximation).
        Citations should use Item labels, not page numbers.
      </p>
    </main>
  </div>
</body>
</html>
"""
