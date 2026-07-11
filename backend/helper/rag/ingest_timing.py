"""Branch-only per-step timing for full 10-K RAG ingest (print + log file)."""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

STEP_ORDER = (
    "sec_fetch",
    "markdown",
    "chunking",
    "db_upsert",
    "embedding",
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LOG_PATH = _REPO_ROOT / ".logs" / "rag_ingest_timing.log"


def filing_timing_key(ticker: str, year: int | None) -> str:
    sym = ticker.strip().upper()
    if year is not None:
        return f"{sym} FY{year}"
    return sym


@dataclass
class _FilingTiming:
    key: str
    cache_hit: bool = False
    steps: dict[str, float] = field(default_factory=dict)
    wall_start: float = field(default_factory=time.perf_counter)
    wall_end: float | None = None


class IngestTimingSession:
    """Collect per-filing step durations across parallel ingest tasks."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._filings: dict[str, _FilingTiming] = {}

    def begin_filing(self, ticker: str, year: int | None = None) -> str:
        key = filing_timing_key(ticker, year)
        with self._lock:
            self._filings[key] = _FilingTiming(key=key)
        return key

    def remkey(self, old_key: str, ticker: str, year: int | None) -> str:
        """Rename filing key once fiscal year is known (e.g. after SEC meta)."""
        new_key = filing_timing_key(ticker, year)
        if old_key == new_key:
            return old_key
        with self._lock:
            row = self._filings.pop(old_key, None)
            if row is None:
                row = _FilingTiming(key=new_key)
            else:
                row.key = new_key
            self._filings[new_key] = row
        return new_key

    def mark_cache_hit(self, key: str) -> None:
        with self._lock:
            row = self._filings.get(key)
            if row is None:
                row = _FilingTiming(key=key)
                self._filings[key] = row
            row.cache_hit = True

    def record(self, key: str, step: str, seconds: float) -> None:
        with self._lock:
            row = self._filings.get(key)
            if row is None:
                row = _FilingTiming(key=key)
                self._filings[key] = row
            row.steps[step] = row.steps.get(step, 0.0) + seconds

    def finish_filing(self, key: str) -> None:
        with self._lock:
            row = self._filings.get(key)
            if row is not None:
                row.wall_end = time.perf_counter()

    @contextmanager
    def step(self, key: str, step: str) -> Iterator[None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.record(key, step, time.perf_counter() - t0)

    def format_summary(self) -> str:
        with self._lock:
            rows = sorted(self._filings.values(), key=lambda r: r.key)
        lines = ["=== RAG ingest timing ==="]
        if not rows:
            lines.append("(no filings timed)")
            return "\n".join(lines)

        for row in rows:
            if row.wall_end is not None:
                total = row.wall_end - row.wall_start
            elif row.steps:
                total = sum(row.steps.values())
            else:
                total = time.perf_counter() - row.wall_start
            hit = "  cache_hit=true" if row.cache_hit else ""
            lines.append(f"{row.key}  total={total:.2f}s{hit}")
            if row.cache_hit and not row.steps:
                lines.append("  (skipped sec_fetch/markdown/chunking/db_upsert/embedding)")
                continue
            for step in STEP_ORDER:
                if step in row.steps:
                    note = "  # includes section analyze" if step == "chunking" else ""
                    lines.append(f"  {step}={row.steps[step]:.2f}s{note}")
            extras = [s for s in row.steps if s not in STEP_ORDER]
            for step in extras:
                lines.append(f"  {step}={row.steps[step]:.2f}s")
        return "\n".join(lines)

    def emit(self) -> None:
        summary = self.format_summary()
        print(summary, flush=True)
        try:
            _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            with _LOG_PATH.open("a", encoding="utf-8") as fh:
                fh.write(f"\n[{stamp}]\n{summary}\n")
        except OSError as exc:
            print(f"(could not write {_LOG_PATH}: {exc})", flush=True)
