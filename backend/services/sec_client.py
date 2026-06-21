"""SEC EDGAR HTTP client — ticker lookup and company facts."""

from __future__ import annotations

import os
import re
import time
from functools import lru_cache

import httpx

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

_last_request_at = 0.0
_MIN_INTERVAL = 0.12  # ~8 req/s, under SEC 10/s guidance


def _user_agent() -> str:
    return (
        os.getenv("SEC_USER_AGENT", "").strip()
        or "FinancialModelBuilder contact@example.com"
    )


def _throttle() -> None:
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request_at = time.monotonic()


def _get(url: str) -> dict:
    _throttle()
    headers = {
        "User-Agent": _user_agent(),
        "Accept": "application/json",
    }
    with httpx.Client(timeout=60.0, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


@lru_cache(maxsize=1)
def load_ticker_index() -> list[dict]:
    """Return [{ticker, cik, title}, ...] from SEC company_tickers.json."""
    raw = _get(SEC_TICKERS_URL)
    entries: list[dict] = []
    for item in raw.values():
        entries.append(
            {
                "ticker": str(item["ticker"]).upper(),
                "cik": str(item["cik_str"]).zfill(10),
                "title": str(item["title"]),
            }
        )
    return entries


def resolve_ticker(
    *,
    company_name: str | None = None,
    ticker: str | None = None,
) -> dict:
    """Resolve or validate a US listing ticker."""
    index = load_ticker_index()
    if ticker:
        sym = ticker.strip().upper()
        for entry in index:
            if entry["ticker"] == sym:
                return {
                    "ticker": entry["ticker"],
                    "cik": entry["cik"],
                    "entity_name": entry["title"],
                    "matched_by": "ticker",
                }
        return {"error": f"Ticker '{sym}' not found in SEC company list"}

    if not company_name or not company_name.strip():
        return {"error": "Provide company_name or ticker"}

    name = company_name.strip().lower()
    name_compact = re.sub(r"[^a-z0-9]", "", name)
    candidates: list[tuple[int, dict]] = []

    for entry in index:
        title = entry["title"].lower()
        title_compact = re.sub(r"[^a-z0-9]", "", title)
        score = 0
        if name == title or name_compact == title_compact:
            score = 100
        elif name in title or title in name:
            score = 80
        elif name_compact in title_compact or title_compact in name_compact:
            score = 60
        if score:
            candidates.append((score, entry))

    if not candidates:
        return {"error": f"No SEC listing found for '{company_name}'"}

    candidates.sort(key=lambda x: (-x[0], len(x[1]["title"])))
    best = candidates[0][1]
    return {
        "ticker": best["ticker"],
        "cik": best["cik"],
        "entity_name": best["title"],
        "matched_by": "company_name",
    }


def fetch_company_facts(cik: str) -> dict:
    padded = str(cik).zfill(10)
    return _get(SEC_FACTS_URL.format(cik=padded))
