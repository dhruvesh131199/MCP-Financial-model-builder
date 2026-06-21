"""GAAP XBRL tag aliases → canonical statement line items."""

INCOME_CONCEPTS: dict[str, list[str]] = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "cost_of_revenue": [
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss"],
    "eps_basic": ["EarningsPerShareBasic"],
    "eps_diluted": ["EarningsPerShareDiluted"],
}

BALANCE_CONCEPTS: dict[str, list[str]] = {
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "stockholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsAndShortTermInvestments",
    ],
    "long_term_debt": [
        "LongTermDebt",
        "LongTermDebtNoncurrent",
    ],
    "shares_outstanding": ["CommonStockSharesOutstanding"],
}

CASHFLOW_CONCEPTS: dict[str, list[str]] = {
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
}

STATEMENT_CONCEPTS: dict[str, dict[str, list[str]]] = {
    "income": INCOME_CONCEPTS,
    "balance": BALANCE_CONCEPTS,
    "cashflow": CASHFLOW_CONCEPTS,
}

LINE_LABELS: dict[str, str] = {
    "revenue": "Revenue",
    "cost_of_revenue": "Cost of Revenue",
    "gross_profit": "Gross Profit",
    "operating_income": "Operating Income",
    "net_income": "Net Income",
    "eps_basic": "EPS (Basic)",
    "eps_diluted": "EPS (Diluted)",
    "total_assets": "Total Assets",
    "total_liabilities": "Total Liabilities",
    "stockholders_equity": "Stockholders' Equity",
    "cash": "Cash & Equivalents",
    "long_term_debt": "Long-Term Debt",
    "shares_outstanding": "Shares Outstanding",
    "operating_cash_flow": "Operating Cash Flow",
    "capex": "Capital Expenditures",
    "free_cash_flow": "Free Cash Flow",
}
