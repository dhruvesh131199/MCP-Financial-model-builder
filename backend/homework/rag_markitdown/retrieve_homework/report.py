"""Write retrieve homework test report (JSON + HTML)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from homework.rag_markitdown.hf_rerank import RerankHit
from homework.rag_markitdown.postgres_search import VectorHit


@dataclass
class RetrieveTestReport:
    query: str
    embed_model: str
    rerank_model: str
    ticker: str
    year: int
    doctype: str
    vector_limit: int
    vector_hit_count: int
    created_at: str
    vector_hits: list[VectorHit]
    reranked_hits: list[RerankHit]

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "embed_model": self.embed_model,
            "rerank_model": self.rerank_model,
            "ticker": self.ticker,
            "year": self.year,
            "doctype": self.doctype,
            "vector_limit": self.vector_limit,
            "vector_hit_count": self.vector_hit_count,
            "created_at": self.created_at,
            "vector_hits": [asdict(h) for h in self.vector_hits],
            "reranked_hits": [asdict(h) for h in self.reranked_hits],
        }


def write_report(out_dir: Path, report: RetrieveTestReport) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "retrieve_test_report.json"
    json_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    html_path = out_dir / "retrieve_test_report.html"
    html_path.write_text(_report_html(report), encoding="utf-8")
    return json_path


def preview_text(text: str, max_len: int = 120) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_len:
        return collapsed
    return collapsed[: max_len - 1] + "…"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _delta_cell(delta: int) -> str:
    if delta > 0:
        return f'<span class="up">+{delta}</span>'
    if delta < 0:
        return f'<span class="down">{delta}</span>'
    return '<span class="same">0</span>'


def _vector_rows(hits: list[VectorHit]) -> str:
    parts: list[str] = []
    for hit in hits:
        parts.append(
            f"<tr>"
            f"<td>{hit.vector_rank}</td>"
            f"<td>{hit.vector_score:.4f}</td>"
            f"<td><code>{_escape(hit.parent_id)}</code></td>"
            f"<td>{hit.chunk_index}</td>"
            f"<td><code>{_escape(hit.sub_id[:8])}…</code></td>"
            f"<td>{_escape(preview_text(hit.content))}</td>"
            f"</tr>"
            f'<tr class="detail"><td colspan="6"><details>'
            f"<summary>Full content</summary>"
            f"<pre>{_escape(hit.content)}</pre>"
            f"</details></td></tr>"
        )
    return "".join(parts)


def _rerank_rows(hits: list[RerankHit]) -> str:
    parts: list[str] = []
    for hit in hits:
        parts.append(
            f"<tr>"
            f"<td>{hit.rerank_rank}</td>"
            f"<td>{hit.rerank_score:.4f}</td>"
            f"<td>{hit.vector_rank}</td>"
            f"<td>{_delta_cell(hit.rank_delta)}</td>"
            f"<td><code>{_escape(hit.parent_id)}</code></td>"
            f"<td>{hit.chunk_index}</td>"
            f"<td>{_escape(preview_text(hit.content))}</td>"
            f"</tr>"
            f'<tr class="detail"><td colspan="7"><details>'
            f"<summary>Full content</summary>"
            f"<pre>{_escape(hit.content)}</pre>"
            f"</details></td></tr>"
        )
    return "".join(parts)


def _report_html(report: RetrieveTestReport) -> str:
    filing = f"{report.ticker} · {report.doctype} · FY{report.year}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>RAG retrieve test — {report.ticker}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 1100px; line-height: 1.45; }}
    h1, h2 {{ margin-top: 1.5rem; }}
    .flow {{ display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;
             padding: 1rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; }}
    .flow span {{ padding: 0.35rem 0.6rem; background: #fff; border: 1px solid #cbd5e1; border-radius: 6px; }}
    .arrow {{ color: #64748b; font-weight: bold; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 0.75rem; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; vertical-align: top; }}
    th {{ background: #f5f5f5; }}
    tr.detail td {{ background: #fafafa; border-top: none; }}
    code {{ font-size: 0.85em; }}
    pre {{ white-space: pre-wrap; word-break: break-word; font-size: 0.85em; margin: 0.5rem 0; }}
    .up {{ color: #15803d; font-weight: 600; }}
    .down {{ color: #b91c1c; font-weight: 600; }}
    .same {{ color: #64748b; }}
    .meta {{ color: #475569; }}
  </style>
</head>
<body>
  <h1>RAG retrieval homework</h1>
  <p class="meta"><strong>Query:</strong> {_escape(report.query)}</p>
  <p class="meta"><strong>Filing:</strong> {filing} · <strong>Vector hits:</strong> {report.vector_hit_count}</p>
  <p class="meta"><strong>Embed model:</strong> {report.embed_model} · <strong>Rerank model:</strong> {report.rerank_model}</p>

  <div class="flow">
    <span>Query</span><span class="arrow">→</span>
    <span>Embed (HF)</span><span class="arrow">→</span>
    <span>Postgres top {report.vector_limit}</span><span class="arrow">→</span>
    <span>Rerank (HF)</span><span class="arrow">→</span>
    <span>Report</span>
  </div>

  <h2>Stage 1 — Vector retrieval (pgvector)</h2>
  <p class="meta">Cosine similarity from stored sub-chunk embeddings. Higher score = closer match.</p>
  <table>
    <thead><tr>
      <th>Rank</th><th>Score</th><th>Parent</th><th>Chunk #</th><th>Sub ID</th><th>Preview</th>
    </tr></thead>
    <tbody>{_vector_rows(report.vector_hits)}</tbody>
  </table>

  <h2>Stage 2 — After reranking (cross-encoder)</h2>
  <p class="meta">Δ rank = vector rank − rerank rank (positive = moved up after rerank).</p>
  <table>
    <thead><tr>
      <th>Rerank</th><th>Score</th><th>Was #</th><th>Δ</th><th>Parent</th><th>Chunk #</th><th>Preview</th>
    </tr></thead>
    <tbody>{_rerank_rows(report.reranked_hits)}</tbody>
  </table>
</body>
</html>"""
