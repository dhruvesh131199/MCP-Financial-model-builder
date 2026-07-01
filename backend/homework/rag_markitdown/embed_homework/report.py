"""Write embed homework test report (JSON + optional HTML)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ChunkHit:
    sub_id: str
    parent_id: str
    item_label: str | None
    score: float
    preview: str
    rank: int


@dataclass
class EmbedTestReport:
    model_id: str
    dimension: int
    query: str
    chunk_count: int
    source: str
    created_at: str
    hits: list[ChunkHit]

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "dimension": self.dimension,
            "query": self.query,
            "chunk_count": self.chunk_count,
            "source": self.source,
            "created_at": self.created_at,
            "hits": [asdict(h) for h in self.hits],
        }


def write_report(out_dir: Path, report: EmbedTestReport) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "embed_test_report.json"
    json_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    html_path = out_dir / "embed_test_report.html"
    html_path.write_text(_report_html(report), encoding="utf-8")
    return json_path


def _report_html(report: EmbedTestReport) -> str:
    rows = "".join(
        f"<tr><td>{h.rank}</td><td>{h.score:.4f}</td>"
        f"<td><code>{h.parent_id}</code></td>"
        f"<td>{h.item_label or '—'}</td>"
        f"<td>{_escape(h.preview)}</td></tr>"
        for h in report.hits
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Embed test — {report.model_id}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 960px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; vertical-align: top; }}
    th {{ background: #f5f5f5; }}
    code {{ font-size: 0.85em; }}
  </style>
</head>
<body>
  <h1>RAG embed homework test</h1>
  <p><strong>Model:</strong> {report.model_id} ({report.dimension} dims)</p>
  <p><strong>Query:</strong> {_escape(report.query)}</p>
  <p><strong>Chunks tested:</strong> {report.chunk_count} · <strong>Source:</strong> {report.source}</p>
  <table>
    <thead><tr><th>Rank</th><th>Score</th><th>Parent</th><th>Item</th><th>Preview</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>"""


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def preview_text(text: str, max_len: int = 120) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_len:
        return collapsed
    return collapsed[: max_len - 1] + "…"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
