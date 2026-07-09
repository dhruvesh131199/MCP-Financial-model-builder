"""MCP progress reporting for long-running tools."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

JUST_FINANCIALS_STEPS_PER_TICKER = 6
FULL_REPORT_LIST_YEARS_STEPS = 1
FULL_REPORT_STEPS_PER_FILING = 9
EMBED_BATCH_RESERVE = 3


@runtime_checkable
class ProgressReporter(Protocol):
    async def tick(self, message: str) -> None: ...

    def sync_hook(self) -> Callable[[str], None]: ...


def plan_just_financials_steps(ticker_count: int) -> int:
    return max(1, ticker_count) * JUST_FINANCIALS_STEPS_PER_TICKER


def plan_full_report_steps(
    ticker_count: int,
    *,
    filings_per_ticker: list[int],
    needs_year_listing: bool,
) -> int:
    """Estimate total progress steps for full_report."""
    listing = FULL_REPORT_LIST_YEARS_STEPS * ticker_count if needs_year_listing else 0
    filings = sum(
        max(1, count) * (FULL_REPORT_STEPS_PER_FILING + EMBED_BATCH_RESERVE)
        for count in filings_per_ticker
    )
    return max(1, listing + filings)


@dataclass
class NoOpProgressReporter:
    """Default reporter for tests and callers without MCP context."""

    async def tick(self, message: str) -> None:
        return None

    def sync_hook(self) -> Callable[[str], None]:
        return lambda _message: None

    def adjust_total(self, delta: int) -> None:
        return None


@dataclass
class McpProgressReporter:
    """Reports progress + log messages to the MCP client."""

    ctx: Any
    total_steps: int
    done: int = 0
    _pending: list[asyncio.Future[None]] = field(default_factory=list)

    def adjust_total(self, delta: int) -> None:
        if delta:
            self.total_steps = max(self.done + 1, self.total_steps + delta)

    async def tick(self, message: str) -> None:
        self.done = min(self.done + 1, self.total_steps)
        await self.ctx.info(message)
        await self.ctx.report_progress(
            progress=self.done,
            total=self.total_steps,
            message=message,
        )

    def sync_hook(self) -> Callable[[str], None]:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return lambda _message: None

        def on_step(message: str) -> None:
            future = asyncio.run_coroutine_threadsafe(self.tick(message), loop)
            self._pending.append(future)

        return on_step

    async def flush(self) -> None:
        if not self._pending:
            return
        pending = self._pending
        self._pending = []
        for future in pending:
            await asyncio.wrap_future(future)
