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
  da: number;
  ebit: number;
  taxes: number;
  capex: number;
  nwc: number;
  delta_nwc: number;
  ufcf: number;
  fcf: number;
  terminal_value: number;
  total_ufcf: number;
  discount_factor: number;
  pv_fcf: number;
}

export interface DcfInputs {
  base_revenue: number;
  revenue_growth: number | number[];
  ebitda_margin: number | number[];
  da_pct: number | number[];
  tax_rate: number | number[];
  capex_pct: number | number[];
  nwc_pct: number | number[];
  wacc: number;
  terminal_growth: number;
  projection_years: number;
  net_debt?: number | null;
  shares_outstanding?: number | null;
}

export interface DcfReferenceRow {
  key: string;
  label: string;
  values: (number | null)[];
  format: string;
}

export interface DcfReferenceHints {
  base_revenue_m?: number | null;
  shares_outstanding_m?: number | null;
  shares_source?: string | null;
}

export interface DcfReferenceHistory {
  ticker: string;
  company_name?: string | null;
  fiscal_years: number[];
  rows: DcfReferenceRow[];
  latest_revenue_usd?: number | null;
  hints?: DcfReferenceHints;
  units_note?: string;
}

export interface DcfDraftInputs {
  base_revenue: number | null;
  wacc: number | null;
  terminal_growth: number | null;
  revenue_growth: (number | null)[];
  ebitda_margin: (number | null)[];
  da_pct: (number | null)[];
  tax_rate: (number | null)[];
  capex_pct: (number | null)[];
  nwc_pct: (number | null)[];
  net_debt?: number | null;
  shares_outstanding?: number | null;
}

export interface DcfDraftDefaults {
  revenue_growth?: number | null;
  tax_rate?: number | null;
  ebitda_margin?: number | null;
  da_pct?: number | null;
  capex_pct?: number | null;
  nwc_pct?: number | null;
}

export interface DcfDraftData {
  type: "dcf_draft";
  ticker: string;
  company_name?: string | null;
  projection_years: number;
  reference_history: DcfReferenceHistory;
  inputs: DcfDraftInputs;
  defaults?: DcfDraftDefaults;
  computed_model_id?: string | null;
}

export interface DcfDraftModelEntry {
  id: string;
  name: string;
  type: "dcf_draft";
  created_at: string;
  updated_at?: string;
  data: DcfDraftData;
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
  updated_at?: string;
  draft_id?: string;
  data: DcfResult & { draft_id?: string };
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
  | DcfDraftModelEntry
  | ComparativeModelEntry
  | DetailedAnalysisModelEntry;

export interface DcfDraftSummary {
  model_id: string;
  projection_years: number;
  ticker?: string;
  missing_required: string[];
  ready: boolean;
  inputs: DcfDraftInputs;
  defaults?: DcfDraftDefaults;
}

export interface DcfComputeResponse {
  success: boolean;
  model_id: string;
  model_name: string;
  draft_model_id: string;
  enterprise_value_millions: number;
  equity_value_millions?: number | null;
  price_per_share?: number | null;
  result: DcfResult;
}

export interface FinancialsFetchLogEntry {
  id: string;
  created_at?: string;
  source?: string;
  tickers: string[];
  years: number[] | null;
  max_years: number | null;
  status: "success" | "partial" | "error";
  results?: Array<{
    ticker: string;
    success: boolean;
    file_id?: string;
    error?: string;
  }>;
  errors?: string[];
}

export interface Workspace {
  session_id: string;
  updated_at: string | null;
  guide_seen?: boolean;
  models: ModelEntry[];
  files: FileEntry[];
  rag_documents?: RagDocumentEntry[];
  financials_fetch_log?: FinancialsFetchLogEntry[];
}

export interface RagDocumentEntry {
  id: string;
  filing_key: string;
  document_id: string | null;
  ticker: string | null;
  year: number | null;
  doctype: string | null;
  label: string;
  source: string;
  status: "ready" | "error";
  error: string | null;
  from_cache: boolean;
  linked_at?: string;
  parent_count?: number;
  subchunk_count?: number;
  report_url?: string;
  raw_url?: string;
  chunks_url?: string;
  has_report?: boolean;
}

export type DashboardSelection =
  | { kind: "none" }
  | { kind: "file"; id: string }
  | { kind: "model"; id: string }
  | { kind: "analysis"; id: string }
  | { kind: "financials_hub" }
  | { kind: "rag_hub" }
  | { kind: "models_hub" };

export interface ModelRecord {
  session_id?: string;
  updated_at: string | null;
  model: DcfResult | null;
}
