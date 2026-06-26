export interface DetailedMetricCell {
  key: string;
  label: string;
  value: number | null;
  xbrl_tag?: string | null;
  row_label?: string | null;
  source_statement?: string | null;
  source?: "xbrl" | "derived" | "n/a";
  warning?: string | null;
  group?: string | null;
}

export interface DetailedAnalysisPeriod {
  fiscal_year: number;
  fiscal_period: string;
  period_end: string;
  income: DetailedMetricCell[];
  balance: DetailedMetricCell[];
  cashflow: DetailedMetricCell[];
  is_bank_style?: boolean;
  accounting_equation_ok?: boolean | null;
}

export interface TrendAnalysisRow {
  key: string;
  label: string;
  row_type: "currency" | "percent" | "eps";
  highlight: boolean;
  values: (number | null)[];
}

export interface TrendAnalysisData {
  fiscal_years: number[];
  rows: TrendAnalysisRow[];
}

export interface DetailedAnalysisData {
  ticker: string;
  entity_name: string;
  cik: string;
  fetched_at: string;
  source: string;
  periods: DetailedAnalysisPeriod[];
  warnings: string[];
  integrity_checks: string[];
  is_bank_style: boolean;
  trend_analysis?: TrendAnalysisData;
}

export interface DetailedAnalysisModelEntry {
  id: string;
  name: string;
  type: "detailed_analysis";
  created_at: string;
  updated_at?: string;
  data: DetailedAnalysisData;
  source?: { ticker: string; statements_ref?: string };
}

export interface LineItem {
  key: string;
  label: string;
  value: number;
  unit: string;
  source?: "xbrl" | "derived";
  xbrl_tag?: string | null;
  derived_from?: string[] | null;
}

export interface CoverageEntry {
  key: string;
  label: string;
  status: "present" | "derived" | "missing" | "not_applicable";
  value?: number | null;
  reason?: string | null;
  xbrl_tag?: string | null;
  derived_from?: string[] | null;
  statement?: string | null;
}

export interface FieldStatus {
  status: "present" | "derived" | "missing" | "not_applicable";
  value?: number | null;
  reason?: string | null;
}

export interface StatementPeriod {
  fiscal_year: number;
  fiscal_period: string;
  period_end?: string | null;
  filed?: string | null;
  form?: string | null;
  line_items: LineItem[];
}

export interface StatementSlice {
  annual: StatementPeriod[];
  quarterly: StatementPeriod[];
}

export interface FinancialStatements {
  ticker: string;
  cik: string;
  entity_name: string;
  fetched_at: string;
  statements: Record<string, StatementSlice>;
  fetch_scope?: string[];
  coverage?: Record<string, CoverageEntry> | null;
}

export interface FileEntry {
  id: string;
  name: string;
  type: "financials";
  dedup_key?: string;
  created_at: string;
  updated_at?: string;
  data: FinancialStatements;
}

export interface DcfYearRow {
  year: number;
  revenue: number;
  ebitda: number;
  fcf: number;
  pv_fcf: number;
}

export interface DcfInputs {
  base_revenue: number;
  revenue_growth: number | number[];
  ebitda_margin: number;
  tax_rate: number;
  capex_pct: number;
  nwc_pct: number;
  wacc: number;
  terminal_growth: number;
  projection_years: number;
  net_debt?: number | null;
  shares_outstanding?: number | null;
}

export interface DcfResult {
  inputs: DcfInputs;
  years: DcfYearRow[];
  terminal_value: number;
  pv_terminal: number;
  enterprise_value: number;
  equity_value?: number | null;
  price_per_share?: number | null;
  company_name?: string | null;
}

export interface DcfModelEntry {
  id: string;
  name: string;
  type: "dcf";
  created_at: string;
  data: DcfResult;
}

export interface ComparativeFundamentals {
  fiscal_year?: number;
  revenue?: number | null;
  net_income?: number | null;
  gross_margin?: number | null;
  operating_margin?: number | null;
  net_margin?: number | null;
  roe?: number | null;
  roa?: number | null;
  net_debt?: number | null;
  revenue_growth_yoy?: number | null;
  free_cash_flow?: number | null;
  fcf_margin?: number | null;
  book_value_per_share?: number | null;
  ebitda?: number | null;
  eps_diluted?: number | null;
  shares_outstanding?: number | null;
  missing_metrics?: string[];
  field_status?: Record<string, FieldStatus>;
}

export interface ComparativeMultiples {
  stock_price?: number | null;
  market_cap_usd?: number | null;
  market_enterprise_value?: number | null;
  pe_ratio?: number | null;
  pb_ratio?: number | null;
  ev_to_sales?: number | null;
  ev_to_ebitda?: number | null;
}

export interface ComparativeCompanyRow {
  ticker: string;
  company_name?: string | null;
  is_target: boolean;
  fundamentals: ComparativeFundamentals;
  market_data: {
    stock_price?: number | null;
    market_cap_usd?: number | null;
    as_of?: string | null;
    source?: string | null;
    exchange?: string | null;
    industry?: string | null;
    errors?: string[];
    ok?: boolean;
  };
  multiples: ComparativeMultiples;
}

export interface ComparativeReport {
  model_type: "comparative";
  fiscal_year_used: number;
  fiscal_year_note?: string | null;
  target: { ticker?: string; company_name?: string | null };
  peers: { ticker?: string; company_name?: string | null }[];
  companies: ComparativeCompanyRow[];
  summary: Record<string, number | null | undefined>;
  market_data_errors?: string[];
}

export interface ComparativeModelEntry {
  id: string;
  name: string;
  type: "comparative";
  created_at: string;
  data: ComparativeReport;
}

export type ModelEntry =
  | DcfModelEntry
  | ComparativeModelEntry
  | DetailedAnalysisModelEntry;

export interface Workspace {
  session_id: string;
  updated_at: string | null;
  models: ModelEntry[];
  files: FileEntry[];
}

export type DashboardSelection =
  | { kind: "none" }
  | { kind: "file"; id: string }
  | { kind: "model"; id: string }
  | { kind: "analysis"; id: string };

export interface ModelRecord {
  session_id?: string;
  updated_at: string | null;
  model: DcfResult | null;
}
