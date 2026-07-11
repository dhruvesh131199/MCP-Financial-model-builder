"""Unit tests for branch-only RAG ingest timing helper."""

from __future__ import annotations

import time

from helper.rag.ingest_timing import IngestTimingSession, filing_timing_key


def test_filing_timing_key():
    assert filing_timing_key("aapl", 2025) == "AAPL FY2025"
    assert filing_timing_key("WMT", None) == "WMT"


def test_format_summary_steps_and_cache_hit():
    s = IngestTimingSession()
    k = s.begin_filing("AAPL", 2025)
    with s.step(k, "sec_fetch"):
        time.sleep(0.005)
    with s.step(k, "markdown"):
        time.sleep(0.005)
    s.finish_filing(k)

    k2 = s.begin_filing("COST", 2025)
    s.mark_cache_hit(k2)
    s.finish_filing(k2)

    text = s.format_summary()
    assert "=== RAG ingest timing ===" in text
    assert "AAPL FY2025" in text
    assert "sec_fetch=" in text
    assert "markdown=" in text
    assert "COST FY2025" in text
    assert "cache_hit=true" in text
    assert "skipped sec_fetch" in text


def test_remkey_preserves_steps():
    s = IngestTimingSession()
    k = s.begin_filing("MU", None)
    with s.step(k, "sec_fetch"):
        time.sleep(0.002)
    k2 = s.remkey(k, "MU", 2025)
    assert k2 == "MU FY2025"
    s.finish_filing(k2)
    text = s.format_summary()
    assert "MU FY2025" in text
    assert "sec_fetch=" in text
