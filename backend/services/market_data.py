"""Market data via Finnhub — quote + company profile."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx

FINNHUB_BASE = "https://finnhub.io/api/v1"


def _finnhub_api_key() -> str:
    return os.getenv("FINNHUB_API_KEY", "").strip()


def verify_finnhub_config() -> dict[str, Any]:
    key = _finnhub_api_key()
    if not key:
        return {
            "ok": False,
            "error": "FINNHUB_API_KEY is not configured in the MCP/API process environment",
        }
    return {"ok": True, "error": None}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_json(path: str, params: dict[str, str]) -> dict[str, Any]:
    api_key = _finnhub_api_key()
    if not api_key:
        raise ValueError("FINNHUB_API_KEY is not configured")
    query = {**params, "token": api_key}
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(f"{FINNHUB_BASE}{path}", params=query)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise ValueError("Finnhub rate limit exceeded (429)") from exc
        raise ValueError(f"Finnhub HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise ValueError(f"Finnhub request failed: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Unexpected Finnhub response")
    return data


def fetch_quote(ticker: str) -> dict[str, Any] | None:
    """Fetch last price from /quote. Returns None on empty/invalid quote."""
    sym = ticker.strip().upper()
    data = _get_json("/quote", {"symbol": sym})
    price = data.get("c")
    if price is None or float(price) <= 0:
        return None
    return {
        "stock_price": float(price),
        "previous_close": float(data["pc"]) if data.get("pc") else None,
    }


def fetch_profile(ticker: str) -> dict[str, Any] | None:
    """Fetch company profile from /stock/profile2."""
    sym = ticker.strip().upper()
    data = _get_json("/stock/profile2", {"symbol": sym})
    if not data or not data.get("ticker"):
        return None
    market_cap_m = data.get("marketCapitalization")
    shares_m = data.get("shareOutstanding")
    return {
        "company_name": data.get("name"),
        "exchange": data.get("exchange"),
        "industry": data.get("finnhubIndustry"),
        "currency": data.get("currency"),
        "market_cap_usd": float(market_cap_m) * 1_000_000 if market_cap_m else None,
        "shares_outstanding": float(shares_m) * 1_000_000 if shares_m else None,
    }


def fetch_market_snapshot(
    ticker: str,
    *,
    sec_shares_outstanding: float | None = None,
) -> dict[str, Any]:
    """
    Combine Finnhub quote + profile2 into one market snapshot.
    Free tier: /quote + /stock/profile2, 60 calls/min.
    """
    sym = ticker.strip().upper()
    errors: list[str] = []
    as_of = _utc_now_iso()

    config = verify_finnhub_config()
    if not config["ok"]:
        return {
            "ticker": sym,
            "stock_price": None,
            "market_cap_usd": None,
            "shares_outstanding": None,
            "as_of": as_of,
            "source": "finnhub",
            "errors": [config["error"]],
            "ok": False,
        }

    quote: dict[str, Any] | None = None
    profile: dict[str, Any] | None = None

    try:
        quote = fetch_quote(sym)
    except ValueError as exc:
        errors.append(f"quote: {exc}")

    try:
        profile = fetch_profile(sym)
    except ValueError as exc:
        errors.append(f"profile: {exc}")

    stock_price: float | None = quote.get("stock_price") if quote else None
    market_cap_usd: float | None = profile.get("market_cap_usd") if profile else None
    shares_outstanding: float | None = (
        profile.get("shares_outstanding") if profile else None
    )

    if stock_price is None and market_cap_usd and shares_outstanding:
        stock_price = market_cap_usd / shares_outstanding
        errors.append("quote: derived price from profile market cap / shares")

    if market_cap_usd is None and stock_price is not None:
        shares_for_cap = sec_shares_outstanding or shares_outstanding
        if shares_for_cap:
            market_cap_usd = stock_price * shares_for_cap
            errors.append("profile: derived market cap from price × shares")

    return {
        "ticker": sym,
        "stock_price": stock_price,
        "market_cap_usd": market_cap_usd,
        "shares_outstanding": shares_outstanding,
        "company_name": profile.get("company_name") if profile else None,
        "exchange": profile.get("exchange") if profile else None,
        "industry": profile.get("industry") if profile else None,
        "as_of": as_of,
        "source": "finnhub",
        "errors": errors,
        "ok": stock_price is not None or market_cap_usd is not None,
    }
