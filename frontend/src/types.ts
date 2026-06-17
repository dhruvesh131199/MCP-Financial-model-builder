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
  files: never[];
}

export type DashboardSelection =
  | { kind: "none" }
  | { kind: "model"; id: string };

export interface ModelRecord {
  session_id?: string;
  updated_at: string | null;
  model: DcfResult | null;
}
