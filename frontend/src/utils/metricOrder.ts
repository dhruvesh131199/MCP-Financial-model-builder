/** Canonical line-item order — mirrors backend ingest/metric_catalog.py */

export const INCOME_METRIC_ORDER = [
  "revenue",
  "cost_of_revenue",
  "gross_profit",
  "research_and_development",
  "selling_general_admin",
  "operating_income",
  "depreciation_and_amortization",
  "depreciation",
  "amortization",
  "ebitda",
  "interest_expense",
  "income_before_tax",
  "income_tax_expense",
  "net_income",
  "eps_basic",
  "eps_diluted",
  "weighted_avg_shares_basic",
  "weighted_avg_shares_diluted",
] as const;

export const BALANCE_METRIC_ORDER = [
  "cash",
  "short_term_investments",
  "total_assets",
  "total_liabilities",
  "stockholders_equity",
  "short_term_debt",
  "long_term_debt",
  "total_debt",
  "shares_outstanding",
] as const;

export const CASHFLOW_METRIC_ORDER = [
  "depreciation_and_amortization",
  "operating_cash_flow",
  "investing_cash_flow",
  "capex",
  "free_cash_flow",
  "financing_cash_flow",
  "net_cash_change",
] as const;

export const DETAILED_INCOME_ORDER = [
  "revenue",
  "cost_of_revenue",
  "gross_profit",
  "operating_cost",
  "operating_income",
  "ebitda",
  "depreciation",
  "amortization",
  "interest_expense",
  "income_tax_expense",
  "net_income",
  "eps_diluted",
] as const;

export const DETAILED_BALANCE_ORDER = [
  "current_assets",
  "non_current_assets",
  "total_assets",
  "current_liabilities",
  "non_current_liabilities",
  "total_liabilities",
  "stockholders_equity",
  "cash_end_of_period",
] as const;

export const DETAILED_CASHFLOW_ORDER = [
  "operating_cash_flow",
  "investing_cash_flow",
  "free_cash_flow",
  "financing_cash_flow",
  "net_cash_change",
] as const;

export const DETAILED_ANALYSIS_ORDER: Record<string, readonly string[]> = {
  income: DETAILED_INCOME_ORDER,
  balance: DETAILED_BALANCE_ORDER,
  cashflow: DETAILED_CASHFLOW_ORDER,
};

export const BALANCE_GROUP_LABELS: Record<string, string> = {
  current_assets: "Assets",
  non_current_assets: "Assets",
  total_assets: "Totals",
  current_liabilities: "Liabilities",
  non_current_liabilities: "Liabilities",
  total_liabilities: "Totals",
  stockholders_equity: "Equity",
  cash_end_of_period: "Cash",
};

export const DETAILED_ANALYSIS_DISCLAIMER =
  "Data is fetched from official SEC filings via the edgartools library. We map thousands of XBRL tags using hardcoded rules, but filers use inconsistent labels and tags — some figures may be inaccurate. Please verify against the 10-K/10-Q and treat these as a starting point. We continuously improve our mapping dictionary; thank you for flagging mismatches.";

export const BANK_SECTOR_DISCLAIMER =
  "Bank / financial institution: income statement layout differs from industrial companies (often no COGS or gross profit). Figures may not match standard templates — verify carefully.";

export const FCF_FOOTNOTE =
  "Free cash flow = operating cash flow minus |capital expenditures|. Other sites may use different definitions (leases, working capital, etc.).";

export const DETAILED_METRIC_LABELS: Record<string, string> = {
  revenue: "Revenue",
  cost_of_revenue: "COGS",
  gross_profit: "Gross Profit",
  operating_cost: "Operating Cost",
  operating_income: "Operating Income / EBIT",
  ebitda: "EBITDA",
  depreciation: "Depreciation",
  amortization: "Amortization",
  interest_expense: "Interest",
  income_tax_expense: "Tax",
  net_income: "Net Income",
  eps_diluted: "EPS (Diluted)",
  current_assets: "Current Assets",
  non_current_assets: "Non-Current Assets",
  total_assets: "Total Assets",
  current_liabilities: "Current Liabilities",
  non_current_liabilities: "Non-Current Liabilities",
  total_liabilities: "Total Liabilities",
  stockholders_equity: "Stockholders' Equity",
  cash_end_of_period: "Cash at Period End",
  operating_cash_flow: "CFOA",
  investing_cash_flow: "CFIO (Investing)",
  free_cash_flow: "Free Cash Flow",
  financing_cash_flow: "CFFO (Financing)",
  net_cash_change: "Net Change in Cash (FY)",
};

export const STATEMENT_METRIC_ORDER: Record<string, readonly string[]> = {
  income: INCOME_METRIC_ORDER,
  balance: BALANCE_METRIC_ORDER,
  cashflow: CASHFLOW_METRIC_ORDER,
};

export const METRIC_LABELS: Record<string, string> = {
  revenue: "Revenue",
  cost_of_revenue: "Cost of Revenue",
  gross_profit: "Gross Profit",
  research_and_development: "Research & Development",
  selling_general_admin: "SG&A",
  operating_income: "Operating Income",
  depreciation_and_amortization: "Depreciation & Amortization",
  depreciation: "Depreciation",
  amortization: "Amortization",
  ebitda: "EBITDA",
  interest_expense: "Interest Expense",
  income_before_tax: "Income Before Tax",
  income_tax_expense: "Income Tax Expense",
  net_income: "Net Income",
  eps_basic: "EPS (Basic)",
  eps_diluted: "EPS (Diluted)",
  weighted_avg_shares_basic: "Weighted Avg Shares (Basic)",
  weighted_avg_shares_diluted: "Weighted Avg Shares (Diluted)",
  cash: "Cash & Equivalents",
  short_term_investments: "Short-Term Investments",
  total_assets: "Total Assets",
  total_liabilities: "Total Liabilities",
  stockholders_equity: "Stockholders' Equity",
  short_term_debt: "Short-Term Debt",
  long_term_debt: "Long-Term Debt",
  total_debt: "Total Debt",
  shares_outstanding: "Shares Outstanding",
  operating_cash_flow: "Operating Cash Flow",
  investing_cash_flow: "Investing Cash Flow",
  capex: "Capital Expenditures",
  free_cash_flow: "Free Cash Flow",
  financing_cash_flow: "Financing Cash Flow",
  net_cash_change: "Net Cash Change",
  operating_cost: "Operating Cost",
  current_assets: "Current Assets",
  non_current_assets: "Non-Current Assets",
  current_liabilities: "Current Liabilities",
  non_current_liabilities: "Non-Current Liabilities",
};
