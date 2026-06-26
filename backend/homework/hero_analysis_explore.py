"""
Hero Feature — Phase 1 homework sandbox (edgartools-native, no production ingest).

Fetches 5 years of annual 10-K statements via XBRLS, exports HTML + JSON + CSV
for browsing edgartools output before integrating detailed analysis into the app.

Run from backend/:
    python -m homework.hero_analysis_explore --ticker AAPL
    python -m homework.hero_analysis_explore --ticker JPM --years 5 --open

See: https://edgartools.readthedocs.io/en/latest/guides/financial-data/
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from edgar import Company
from edgar.financials import Financials
from edgar.xbrl import XBRLS

load_dotenv()

from ingest.edgar_identity import ensure_edgar_identity  # noqa: E402
from ingest.fiscal_calendar import fiscal_year_from_period_end  # noqa: E402

OUTPUT_ROOT = Path(__file__).resolve().parent / "hero_output"

XBRLS_STATEMENTS = (
    ("income", "income_statement"),
    ("balance", "balance_sheet"),
    ("cashflow", "cashflow_statement"),
    ("equity", "statement_of_equity"),
    ("comprehensive_income", "comprehensive_income"),
)

SINGLE_FILING_STATEMENTS = (
    ("income", "income_statement"),
    ("balance", "balance_sheet"),
    ("cashflow", "cashflow_statement"),
    ("equity", "statement_of_equity"),
    ("comprehensive_income", "comprehensive_income"),
)

META_COLUMNS = frozenset(
    {
        "label",
        "concept",
        "standard_concept",
        "preferred_sign",
        "level",
        "abstract",
        "dimension",
        "parent_concept",
        "parent_abstract_concept",
    }
)

PERIOD_COL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


@dataclass
class FilingMeta:
    form: str
    filing_date: str | None
    period_of_report: str | None
    accession_no: str | None


@dataclass
class StatementTables:
    """One statement type: standard + optional summary view DataFrames."""

    standard: pd.DataFrame | None = None
    summary: pd.DataFrame | None = None
    fallback_years: list[dict[str, Any]] = field(default_factory=list)
    warning: str | None = None


@dataclass
class HeroFetchResult:
    ticker: str
    entity_name: str
    cik: str
    fetched_at: str
    source: str
    years_requested: int
    filings: list[FilingMeta]
    statements: dict[str, StatementTables]
    warnings: list[str] = field(default_factory=list)


def _company_fy_end(company: Company) -> str | None:
    for source in (company, getattr(company, "data", None)):
        if source is None:
            continue
        fy = getattr(source, "fiscal_year_end", None)
        if fy:
            return str(fy)
    return None


def _period_end_from_col(col: str) -> str | None:
    text = str(col).split("(")[0].strip()
    if PERIOD_COL_RE.match(text):
        return text
    return None


def period_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if _period_end_from_col(str(c))]


def _fy_header(period_col: str, *, fy_end_mmdd: str | None) -> str:
    end = _period_end_from_col(period_col)
    if not end:
        return str(period_col)
    fy = fiscal_year_from_period_end(end, fy_end_mmdd=fy_end_mmdd)
    if fy is not None:
        return f"FY{fy}"
    return end


def _filing_meta(filing: Any) -> FilingMeta:
    period = getattr(filing, "period_of_report", None)
    period_s = str(period)[:10] if period else None
    filed = getattr(filing, "filing_date", None)
    filed_s = str(filed)[:10] if filed else None
    acc = getattr(filing, "accession_no", None)
    form = getattr(filing, "form", "10-K")
    return FilingMeta(
        form=str(form),
        filing_date=filed_s,
        period_of_report=period_s,
        accession_no=str(acc) if acc else None,
    )


def _statement_to_df(statement: Any, *, view: str | None = None) -> pd.DataFrame | None:
    if statement is None:
        return None
    try:
        if view is not None:
            try:
                return statement.to_dataframe(view=view)
            except TypeError:
                pass
        return statement.to_dataframe()
    except Exception:
        return None


def _fetch_xbrls_statement(
    xbrls: XBRLS,
    method_name: str,
    *,
    views: tuple[str, ...] = ("standard", "summary"),
) -> StatementTables:
    method = getattr(xbrls.statements, method_name, None)
    if method is None:
        return StatementTables(warning=f"XBRLS has no method {method_name}")

    out = StatementTables()
    for view in views:
        try:
            rendered = method(view=view)
        except TypeError:
            rendered = method()
        df = _statement_to_df(rendered)
        if df is None or df.empty:
            continue
        if view == "standard":
            out.standard = df
        elif view == "summary":
            out.summary = df

    if out.standard is None and out.summary is not None:
        out.standard = out.summary
    if out.standard is None:
        # detailed fallback per plan
        try:
            rendered = method(view="detailed")
        except TypeError:
            rendered = method()
        df = _statement_to_df(rendered)
        if df is not None and not df.empty:
            out.standard = df
            out.warning = "Used detailed view (standard/summary empty)"
        else:
            out.warning = "No data for this statement"

    return out


def _fetch_single_filing_statement(
    financials: Any,
    method_name: str,
    *,
    fy_label: str,
) -> pd.DataFrame | None:
    method = getattr(financials, method_name, None)
    if method is None:
        return None
    for view in ("standard", "summary", "detailed"):
        try:
            rendered = method(view=view)
        except TypeError:
            rendered = method()
        df = _statement_to_df(rendered, view=view if view != "detailed" else None)
        if df is not None and not df.empty:
            df = df.copy()
            df["_fiscal_year"] = fy_label
            return df
    return None


def fetch_hero_analysis(
    *,
    ticker: str,
    years: int = 5,
) -> HeroFetchResult:
    """Fetch multi-year statements via XBRLS; per-filing fallback if stitch fails."""
    sym = ticker.strip().upper()
    company = Company(sym)
    entity_name = str(getattr(company, "name", sym) or sym)
    cik = str(getattr(company, "cik", "") or "")
    fy_end = _company_fy_end(company)
    warnings: list[str] = []

    filings_obj = company.get_filings(form="10-K", amendments=False).head(years)
    filings_list = list(filings_obj)
    filing_meta = [_filing_meta(f) for f in filings_list]

    if not filings_list:
        raise ValueError(f"No 10-K filings found for {sym}")

    if len(filings_list) < years:
        warnings.append(
            f"Requested {years} annual filings but only found {len(filings_list)}"
        )

    statements: dict[str, StatementTables] = {}
    source = "xbrls"

    try:
        xbrls = XBRLS.from_filings(filings_list)
        for key, method_name in XBRLS_STATEMENTS:
            statements[key] = _fetch_xbrls_statement(xbrls, method_name)
            if statements[key].warning and statements[key].standard is None:
                warnings.append(f"{key}: {statements[key].warning}")
    except Exception as exc:
        source = "per_filing_fallback"
        warnings.append(f"XBRLS.from_filings failed ({exc}); using per-filing tables")
        statements = {key: StatementTables() for key, _ in SINGLE_FILING_STATEMENTS}

        for filing in filings_list:
            period = getattr(filing, "period_of_report", None)
            period_end = str(period)[:10] if period else "unknown"
            fy = fiscal_year_from_period_end(period_end, fy_end_mmdd=fy_end)
            fy_label = f"FY{fy}" if fy else period_end

            try:
                fin = Financials.extract(filing)
            except Exception as fin_exc:
                warnings.append(f"Financials.extract failed for {fy_label}: {fin_exc}")
                continue

            for key, method_name in SINGLE_FILING_STATEMENTS:
                df = _fetch_single_filing_statement(
                    fin, method_name, fy_label=fy_label
                )
                if df is not None:
                    statements[key].fallback_years.append(
                        {"fiscal_year": fy_label, "dataframe": df}
                    )

        for key, tables in statements.items():
            if not tables.standard and not tables.fallback_years:
                tables.warning = "No data in fallback mode"

    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return HeroFetchResult(
        ticker=sym,
        entity_name=entity_name,
        cik=cik,
        fetched_at=fetched_at,
        source=source,
        years_requested=years,
        filings=filing_meta,
        statements=statements,
        warnings=warnings,
    )


def _fmt_value(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    try:
        num = float(val)
    except (TypeError, ValueError):
        return html.escape(str(val))
    if abs(num) >= 1e9:
        return f"{num / 1e9:,.2f}B"
    if abs(num) >= 1e6:
        return f"{num / 1e6:,.2f}M"
    if abs(num) >= 1e3:
        return f"{num / 1e3:,.2f}K"
    if num == int(num):
        return f"{int(num):,}"
    return f"{num:,.2f}"


def _display_columns(df: pd.DataFrame, *, fy_end_mmdd: str | None) -> list[tuple[str, str]]:
    """Return (column_id, header_label) pairs for table rendering."""
    cols: list[tuple[str, str]] = []
    for meta in ("label", "concept", "standard_concept"):
        if meta in df.columns:
            cols.append((meta, meta.replace("_", " ").title()))
    for col in period_columns(df):
        cols.append((col, _fy_header(col, fy_end_mmdd=fy_end_mmdd)))
    return cols


def _dataframe_to_html_table(
    df: pd.DataFrame,
    *,
    fy_end_mmdd: str | None,
    table_id: str,
) -> str:
    if df is None or df.empty:
        return '<p class="empty">No data</p>'

    display_cols = _display_columns(df, fy_end_mmdd=fy_end_mmdd)
    if not display_cols:
        display_cols = [(str(c), str(c)) for c in df.columns]

    header = "".join(f"<th>{html.escape(h)}</th>" for _, h in display_cols)
    rows_html: list[str] = []
    for _, row in df.iterrows():
        label_val = str(row.get("label", ""))
        cells = []
        for col_id, _ in display_cols:
            val = row.get(col_id)
            if col_id in META_COLUMNS and col_id != "label":
                text = html.escape(str(val)) if val is not None and not pd.isna(val) else "—"
            else:
                text = _fmt_value(val)
            cells.append(f"<td>{text}</td>")
        rows_html.append(
            f'<tr data-label="{html.escape(label_val.lower())}">{"".join(cells)}</tr>'
        )

    return f"""
    <div class="table-wrap">
      <input type="search" class="row-filter" placeholder="Filter rows…"
             data-target="{table_id}" aria-label="Filter table rows" />
      <table id="{table_id}" class="stmt-table">
        <thead><tr>{header}</tr></thead>
        <tbody>{"".join(rows_html)}</tbody>
      </table>
    </div>
    """


def _fallback_section_html(
    fallback_years: list[dict[str, Any]],
    *,
    fy_end_mmdd: str | None,
    prefix: str,
) -> str:
    parts: list[str] = []
    for i, entry in enumerate(fallback_years):
        fy = entry.get("fiscal_year", f"year_{i}")
        df = entry["dataframe"]
        tid = f"{prefix}_{i}"
        parts.append(f'<h3 class="subheading">{html.escape(str(fy))}</h3>')
        parts.append(_dataframe_to_html_table(df, fy_end_mmdd=fy_end_mmdd, table_id=tid))
    return "\n".join(parts)


def build_report_html(result: HeroFetchResult, *, fy_end_mmdd: str | None = None) -> str:
    tab_defs = [
        ("income", "Income Statement"),
        ("balance", "Balance Sheet"),
        ("cashflow", "Cash Flow"),
        ("equity", "Statement of Equity"),
        ("comprehensive_income", "Comprehensive Income"),
    ]

    warnings_html = ""
    if result.warnings:
        items = "".join(f"<li>{html.escape(w)}</li>" for w in result.warnings)
        warnings_html = f'<ul class="warnings">{items}</ul>'

    filings_rows = "".join(
        f"<tr><td>{html.escape(f.form)}</td>"
        f"<td>{html.escape(f.period_of_report or '—')}</td>"
        f"<td>{html.escape(f.filing_date or '—')}</td>"
        f"<td>{html.escape(f.accession_no or '—')}</td></tr>"
        for f in result.filings
    )

    tab_buttons: list[str] = []
    tab_panels: list[str] = []

    for key, title in tab_defs:
        tables = result.statements.get(key, StatementTables())
        tab_buttons.append(
            f'<button type="button" class="tab-btn" data-tab="{key}">{html.escape(title)}</button>'
        )

        if tables.fallback_years:
            body = _fallback_section_html(
                tables.fallback_years,
                fy_end_mmdd=fy_end_mmdd,
                prefix=key,
            )
        elif tables.standard is not None:
            std_html = _dataframe_to_html_table(
                tables.standard,
                fy_end_mmdd=fy_end_mmdd,
                table_id=f"{key}_standard",
            )
            sum_html = ""
            if (
                tables.summary is not None
                and tables.standard is not None
                and not tables.summary.equals(tables.standard)
            ):
                sum_html = (
                    '<h3 class="subheading">Summary view</h3>'
                    + _dataframe_to_html_table(
                        tables.summary,
                        fy_end_mmdd=fy_end_mmdd,
                        table_id=f"{key}_summary",
                    )
                )
            body = std_html + sum_html
        else:
            msg = tables.warning or "No data available for this statement"
            body = f'<p class="empty">{html.escape(msg)}</p>'

        tab_panels.append(
            f'<section class="tab-panel" id="panel-{key}" data-tab="{key}">{body}</section>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(result.ticker)} — Hero Analysis (homework)</title>
  <style>
    :root {{
      --bg: #f8f9fc;
      --card: #fff;
      --border: #e5e7ef;
      --accent: #4f46e5;
      --text: #1f2937;
      --muted: #6b7280;
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
    header .meta {{ color: var(--muted); font-size: 0.875rem; }}
    main {{ padding: 1rem 1.5rem 2rem; max-width: 1400px; margin: 0 auto; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
      margin-bottom: 1rem;
    }}
    .warnings {{ color: #b45309; margin: 0.5rem 0 0; padding-left: 1.25rem; }}
    .tabs {{ display: flex; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 0.75rem; }}
    .tab-btn {{
      border: 1px solid var(--border);
      background: #fff;
      border-radius: 8px;
      padding: 0.45rem 0.75rem;
      font-size: 0.8rem;
      cursor: pointer;
    }}
    .tab-btn.active {{
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }}
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}
    .subheading {{ font-size: 0.95rem; margin: 1rem 0 0.5rem; color: var(--muted); }}
    .table-wrap {{ overflow: auto; max-height: 70vh; border: 1px solid var(--border); border-radius: 8px; }}
    .row-filter {{
      width: 100%;
      padding: 0.5rem 0.75rem;
      border: none;
      border-bottom: 1px solid var(--border);
      font-size: 0.85rem;
    }}
    .stmt-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.8rem;
    }}
    .stmt-table th {{
      position: sticky;
      top: 0;
      background: #f3f4f6;
      text-align: left;
      padding: 0.5rem 0.6rem;
      border-bottom: 1px solid var(--border);
      white-space: nowrap;
    }}
    .stmt-table td {{
      padding: 0.35rem 0.6rem;
      border-bottom: 1px solid #f0f0f5;
      font-variant-numeric: tabular-nums;
    }}
    .stmt-table tr:hover td {{ background: #fafbff; }}
    .empty {{ color: var(--muted); font-style: italic; }}
    .meta-table {{ width: 100%; font-size: 0.8rem; border-collapse: collapse; }}
    .meta-table th, .meta-table td {{
      text-align: left;
      padding: 0.35rem 0.5rem;
      border-bottom: 1px solid var(--border);
    }}
    footer {{
      text-align: center;
      color: var(--muted);
      font-size: 0.75rem;
      padding: 1rem;
    }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(result.entity_name)} ({html.escape(result.ticker)})</h1>
    <div class="meta">
      CIK {html.escape(result.cik)} · Source: {html.escape(result.source)} ·
      {result.years_requested}Y annual · Fetched {html.escape(result.fetched_at)}
    </div>
    {warnings_html}
  </header>
  <main>
    <div class="card">
      <h2 style="margin:0 0 0.5rem;font-size:1rem;">Filings used</h2>
      <table class="meta-table">
        <thead><tr><th>Form</th><th>Period end</th><th>Filed</th><th>Accession</th></tr></thead>
        <tbody>{filings_rows}</tbody>
      </table>
    </div>
    <div class="card">
      <div class="tabs" role="tablist">
        {"".join(tab_buttons)}
      </div>
      {"".join(tab_panels)}
    </div>
  </main>
  <footer>Homework sandbox — not integrated with dashboard. Edgartools output shown as-is.</footer>
  <script>
    const tabs = document.querySelectorAll('.tab-btn');
    const panels = document.querySelectorAll('.tab-panel');
    function activate(tabId) {{
      tabs.forEach(b => b.classList.toggle('active', b.dataset.tab === tabId));
      panels.forEach(p => p.classList.toggle('active', p.dataset.tab === tabId));
    }}
    tabs.forEach(b => b.addEventListener('click', () => activate(b.dataset.tab)));
    if (tabs.length) activate(tabs[0].dataset.tab);

    document.querySelectorAll('.row-filter').forEach(input => {{
      input.addEventListener('input', () => {{
        const table = document.getElementById(input.dataset.target);
        if (!table) return;
        const q = input.value.trim().toLowerCase();
        table.querySelectorAll('tbody tr').forEach(row => {{
          const label = row.dataset.label || '';
          row.style.display = !q || label.includes(q) ? '' : 'none';
        }});
      }});
    }});
  </script>
</body>
</html>"""


def _df_to_json_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        rec: dict[str, Any] = {}
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                rec[str(col)] = None
            elif isinstance(val, (int, float)):
                rec[str(col)] = float(val) if isinstance(val, float) else int(val)
            else:
                rec[str(col)] = str(val)
        records.append(rec)
    return records


def _result_to_json_dict(result: HeroFetchResult) -> dict[str, Any]:
    stmts: dict[str, Any] = {}
    for key, tables in result.statements.items():
        entry: dict[str, Any] = {"warning": tables.warning}
        if tables.standard is not None:
            entry["standard"] = _df_to_json_records(tables.standard)
        if tables.summary is not None and tables.standard is not None:
            if not tables.summary.equals(tables.standard):
                entry["summary"] = _df_to_json_records(tables.summary)
        if tables.fallback_years:
            entry["fallback_years"] = [
                {
                    "fiscal_year": y["fiscal_year"],
                    "rows": _df_to_json_records(y["dataframe"]),
                }
                for y in tables.fallback_years
            ]
        stmts[key] = entry

    return {
        "ticker": result.ticker,
        "entity_name": result.entity_name,
        "cik": result.cik,
        "fetched_at": result.fetched_at,
        "source": result.source,
        "years_requested": result.years_requested,
        "warnings": result.warnings,
        "filings": [
            {
                "form": f.form,
                "filing_date": f.filing_date,
                "period_of_report": f.period_of_report,
                "accession_no": f.accession_no,
            }
            for f in result.filings
        ],
        "statements": stmts,
    }


def export_result(
    result: HeroFetchResult,
    *,
    output_dir: Path | None = None,
) -> Path:
    """Write report.html, raw.json, and CSV files; return output directory."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = output_dir or (OUTPUT_ROOT / f"{result.ticker}_{ts}")
    out_dir.mkdir(parents=True, exist_ok=True)

    company = Company(result.ticker)
    fy_end = _company_fy_end(company)

    report_path = out_dir / "report.html"
    report_path.write_text(
        build_report_html(result, fy_end_mmdd=fy_end), encoding="utf-8"
    )

    json_path = out_dir / "raw.json"
    json_path.write_text(
        json.dumps(_result_to_json_dict(result), indent=2), encoding="utf-8"
    )

    for key, tables in result.statements.items():
        if tables.standard is not None:
            tables.standard.to_csv(out_dir / f"{key}_standard.csv", index=False)
        if (
            tables.summary is not None
            and tables.standard is not None
            and not tables.summary.equals(tables.standard)
        ):
            tables.summary.to_csv(out_dir / f"{key}_summary.csv", index=False)
        for i, entry in enumerate(tables.fallback_years):
            fy = str(entry.get("fiscal_year", i)).replace("/", "-")
            entry["dataframe"].to_csv(
                out_dir / f"{key}_{fy}_fallback.csv", index=False
            )

    return out_dir


def run_explore(
    *,
    ticker: str,
    years: int = 5,
    open_browser: bool = False,
) -> Path:
    ensure_edgar_identity()
    result = fetch_hero_analysis(ticker=ticker, years=years)
    out_dir = export_result(result)
    print(f"Ticker:   {result.ticker} ({result.entity_name})")
    print(f"Source:   {result.source}")
    print(f"Filings:  {len(result.filings)}")
    if result.warnings:
        print("Warnings:")
        for w in result.warnings:
            print(f"  - {w}")
    for key, tables in result.statements.items():
        if tables.standard is not None:
            n_rows = len(tables.standard)
            n_cols = len(period_columns(tables.standard))
            print(f"  {key}: {n_rows} rows, {n_cols} period columns (standard)")
        elif tables.fallback_years:
            print(f"  {key}: {len(tables.fallback_years)} per-filing tables (fallback)")
        else:
            print(f"  {key}: no data ({tables.warning or 'empty'})")
    report_path = out_dir / "report.html"
    print(f"Output:   {report_path}")
    if open_browser:
        webbrowser.open(report_path.as_uri())
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hero Feature homework — fetch 5Y edgartools statements and export HTML"
    )
    parser.add_argument("--ticker", default="AAPL", help="Ticker symbol (default: AAPL)")
    parser.add_argument("--years", type=int, default=5, help="Annual 10-K count (default: 5)")
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open report.html in the default browser after export",
    )
    args = parser.parse_args()

    try:
        run_explore(
            ticker=args.ticker,
            years=args.years,
            open_browser=args.open,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
