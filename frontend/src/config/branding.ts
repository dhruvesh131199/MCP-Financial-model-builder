/** User-facing product name and MCP setup labels (shared across pages). */

export const PRODUCT_NAME = "Financial Analyzer";

export const PRODUCT_TITLE = `${PRODUCT_NAME} Workspace`;

export const HOME_TAGLINE =
  "Your AI-powered workspace for SEC filings, valuations, peer comps, and more. Each session gets a private dashboard link — no signup required.";

export const SETUP_INTRO =
  "Connect our MCP server in Cursor or Claude Desktop, restart once, and run your financial workflow on a private dashboard.";

/** Suggested display name — users can pick any label they like in settings. */
export const MCP_SUGGESTED_NAME = "Financial Workflow";

/** Example JSON key in mcpServers — arbitrary; match whatever you name it in Cursor. */
export const MCP_CONFIG_KEY = "financial-workflow";

export const MCP_SAMPLE_TOOLS = [
  "start_session",
  "fetch_report",
  "create_dcf_model",
  "run_comparative_analysis",
] as const;
