"""Per-retrieve / finalize step timing for query_rag (print + log file)."""

from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LOG_PATH = _REPO_ROOT / ".logs" / "rag_query_timing.log"

RETRIEVE_STEPS = (
    "query_embed",
    "semantic_search",
    "rerank",
    "load_parent",
)

FINALIZE_STEPS = ("build_context",)


class QueryTimingSession:
    """Collect step durations for one query_rag retrieve or finalize call."""

    def __init__(
        self,
        *,
        mode: str,
        ticker: str | None = None,
        loop: int | None = None,
        query: str | None = None,
        embed_provider: str | None = None,
        embed_model: str | None = None,
        embed_dim: int | None = None,
    ) -> None:
        self.mode = mode
        self.ticker = ticker
        self.loop = loop
        self.query = query
        self.embed_provider = embed_provider
        self.embed_model = embed_model
        self.embed_dim = embed_dim
        self.steps: dict[str, float] = {}
        self._wall_start = time.perf_counter()
        self._wall_end: float | None = None

    def record(self, step: str, seconds: float) -> None:
        self.steps[step] = self.steps.get(step, 0.0) + seconds

    @contextmanager
    def step(self, name: str) -> Iterator[None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.record(name, time.perf_counter() - t0)

    def finish(self) -> None:
        self._wall_end = time.perf_counter()

    def format_summary(self) -> str:
        total = (
            (self._wall_end - self._wall_start)
            if self._wall_end is not None
            else sum(self.steps.values())
        )
        lines = [f"=== RAG query timing ({self.mode}) ==="]
        meta_bits: list[str] = []
        if self.ticker:
            meta_bits.append(f"ticker={self.ticker}")
        if self.loop is not None:
            meta_bits.append(f"loop={self.loop}")
        if self.query:
            q = self.query if len(self.query) <= 80 else self.query[:77] + "..."
            meta_bits.append(f'query="{q}"')
        if meta_bits:
            lines.append(" ".join(meta_bits))
        if self.embed_provider or self.embed_model or self.embed_dim is not None:
            lines.append(
                f"  provider={self.embed_provider or '?'} "
                f"model={self.embed_model or '?'} "
                f"dim={self.embed_dim if self.embed_dim is not None else '?'}"
            )
        order = RETRIEVE_STEPS if self.mode == "retrieve" else FINALIZE_STEPS
        for step in order:
            if step in self.steps:
                lines.append(f"  {step}={self.steps[step]:.2f}s")
        for step, sec in self.steps.items():
            if step not in order:
                lines.append(f"  {step}={sec:.2f}s")
        lines.append(f"  total={total:.2f}s")
        return "\n".join(lines)

    def emit(self) -> None:
        if self._wall_end is None:
            self.finish()
        summary = self.format_summary()
        print(summary, flush=True)
        try:
            _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            with _LOG_PATH.open("a", encoding="utf-8") as fh:
                fh.write(f"\n[{stamp}]\n{summary}\n")
        except OSError as exc:
            print(f"(could not write {_LOG_PATH}: {exc})", flush=True)
