"""Shared disclaimer copy for Detailed Analysis UI."""

DETAILED_ANALYSIS_DISCLAIMER = (
    "Data is fetched from official SEC filings via the edgartools library. "
    "We map thousands of XBRL tags using hardcoded rules, but filers use "
    "inconsistent labels and tags — some figures may be inaccurate. "
    "Please verify against the 10-K/10-Q and treat these as a starting point. "
    "We continuously improve our mapping dictionary; thank you for flagging mismatches."
)

BANK_SECTOR_DISCLAIMER = (
    "Bank / financial institution: income statement layout differs from industrial "
    "companies (often no COGS or gross profit). Figures may not match standard "
    "templates — verify carefully."
)

FCF_FOOTNOTE = (
    "Free cash flow = operating cash flow minus |capital expenditures|. "
    "Other sites may use different definitions (leases, working capital, etc.)."
)

NET_CASH_TOOLTIP = (
    "Net change in cash = movement during the fiscal year. "
    "Cash at period end = balance sheet position on the last day of the fiscal year."
)
