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
  "capex",
  "free_cash_flow",
] as const;

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
  capex: "Capital Expenditures",
  free_cash_flow: "Free Cash Flow",
};
