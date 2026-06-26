"""50-ticker universe for HF vs edgartools accuracy study — diverse sectors."""

# fmt: off
TICKERS_50: tuple[str, ...] = (
    # Mega-cap tech (10)
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "INTC", "CRM", "ORCL", "AMZN",
    # Banks & brokers (9)
    "JPM", "BAC", "C", "WFC", "GS", "MS", "USB", "PNC", "SCHW",
    # Payments (4)
    "V", "MA", "PYPL", "AXP",
    # Consumer / retail (10)
    "WMT", "COST", "TGT", "HD", "NKE", "SBUX", "MCD", "KO", "PEP", "PG",
    # Energy (3)
    "XOM", "CVX", "COP",
    # Healthcare (6)
    "JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY",
    # Industrial / transport (4)
    "GE", "CAT", "BA", "UPS",
    # Telecom / media / auto (4)
    "T", "VZ", "TSLA", "GM",
)
# fmt: on

assert len(TICKERS_50) == 50
