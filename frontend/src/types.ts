export interface LineItem {
  key: string;
  label: string;
  value: number;
  unit: string;
}

export interface StatementPeriod {
  fiscal_year: number;
  fiscal_period: string;
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
}

export interface FileEntry {
  id: string;
  name: string;
  type: "financials";
  dedup_key?: string;
  created_at: string;
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

export interface Workspace {
  session_id: string;
  updated_at: string | null;
  models: DcfModelEntry[];
  files: FileEntry[];
}

export type DashboardSelection =
  | { kind: "none" }
  | { kind: "file"; id: string }
  | { kind: "model"; id: string };

export interface ModelRecord {
  session_id?: string;
  updated_at: string | null;
  model: DcfResult | null;
}
