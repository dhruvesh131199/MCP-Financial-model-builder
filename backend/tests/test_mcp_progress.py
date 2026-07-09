"""Tests for MCP progress reporting helpers."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from mcp.progress import (
    FULL_REPORT_LIST_YEARS_STEPS,
    FULL_REPORT_STEPS_PER_FILING,
    JUST_FINANCIALS_STEPS_PER_TICKER,
    McpProgressReporter,
    NoOpProgressReporter,
    plan_full_report_steps,
    plan_just_financials_steps,
)

spec = importlib.util.spec_from_file_location(
    "mcp.fetch_report",
    os.path.abspath(os.path.dirname(__file__) + "/../mcp/fetch_report.py"),
)
fetch_report_mod = importlib.util.module_from_spec(spec)
sys.modules["mcp.fetch_report"] = fetch_report_mod
spec.loader.exec_module(fetch_report_mod)

plan_fetch_report_steps = fetch_report_mod.plan_fetch_report_steps


def test_plan_just_financials_steps():
    assert plan_just_financials_steps(3) == 3 * JUST_FINANCIALS_STEPS_PER_TICKER
    assert plan_fetch_report_steps(
        "just_financials",
        ticker_count=3,
    ) == 18


def test_plan_full_report_steps_with_years():
    total = plan_full_report_steps(
        1,
        filings_per_ticker=[2],
        needs_year_listing=False,
    )
    assert total == 2 * FULL_REPORT_STEPS_PER_FILING

    assert plan_fetch_report_steps(
        "full_report",
        ticker_count=1,
        years=[2023, 2024],
    ) == total


def test_plan_full_report_steps_with_year_listing():
    total = plan_full_report_steps(
        2,
        filings_per_ticker=[1, 1],
        needs_year_listing=True,
    )
    assert total == 2 * FULL_REPORT_LIST_YEARS_STEPS + 2 * FULL_REPORT_STEPS_PER_FILING

    assert plan_fetch_report_steps(
        "full_report",
        ticker_count=2,
        max_years=1,
    ) == total


def test_mcp_progress_reporter_emits_info_and_progress():
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.report_progress = AsyncMock()
    reporter = McpProgressReporter(ctx, total_steps=3)

    async def run() -> None:
        await reporter.tick("step one")
        await reporter.tick("step two")

    asyncio.run(run())

    assert ctx.info.await_count == 2
    assert ctx.report_progress.await_count == 2
    ctx.report_progress.assert_any_call(progress=1, total=3, message="step one")
    ctx.report_progress.assert_any_call(progress=2, total=3, message="step two")


def test_sync_hook_reports_from_worker_thread():
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.report_progress = AsyncMock()
    reporter = McpProgressReporter(ctx, total_steps=2)

    async def run() -> None:
        hook = reporter.sync_hook()
        await asyncio.to_thread(hook, "from worker")
        await reporter.flush()

    asyncio.run(run())

    ctx.info.assert_awaited_once_with("from worker")
    ctx.report_progress.assert_awaited_once_with(
        progress=1,
        total=2,
        message="from worker",
    )


def test_noop_progress_reporter():
    reporter = NoOpProgressReporter()

    async def run() -> None:
        await reporter.tick("ignored")

    asyncio.run(run())
    reporter.sync_hook()("also ignored")
