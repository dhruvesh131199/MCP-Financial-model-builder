/** User-facing product name and MCP setup labels (shared across pages). */

export const PRODUCT_NAME = "Financial Analyzer";

export const PRODUCT_TITLE = `${PRODUCT_NAME} Workspace`;

export const HOME_TAGLINE =
  "Your AI-powered workspace for SEC filings, valuations, peer comps, and more. Each session gets a private dashboard link — no signup required.";

export const HOME_MCP_TITLE = "Create MCP setup";

export const HOME_MCP_DESCRIPTION =
  "Start working by giving prompts in Cursor, Claude, or any MCP-compatible host. Connect once, then run fetch, DCF, comps, and 10-K Q&A from chat.";

export const HOME_EXPLORE_TITLE = "Start exploring without MCP setup";

export const HOME_EXPLORE_DESCRIPTION =
  "Jump straight into the dashboard — fetch SEC filings, build models, and upload 10-Ks from the UI. Add MCP later when you want AI in chat.";

/** Site-wide hours notice — Oracle VM is only running in this window. */
export const HOURS_BANNER_TEXT =
  "This project is live daily from 7:00 AM to 9:00 PM Eastern Time (EST). Outside these hours, the API and MCP server may be unavailable.";

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
  "rag_res_on_display",
] as const;
