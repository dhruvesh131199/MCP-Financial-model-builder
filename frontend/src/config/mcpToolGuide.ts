/**
 * MCP tool reference for the dashboard Tool Guide popup.
 * UPDATE THIS FILE when adding a tool or changing tool behavior in backend/mcp/server.py.
 */

export interface McpToolGuideEntry {
  tool: string;
  summary: string;
  examples: [string, string?];
}

export const MCP_TOOL_GUIDE: McpToolGuideEntry[] = [
  {
    tool: "start_session",
    summary:
      "Create a new workspace or attach to an existing one. Run first — use the session_id from the response on every later call.",
    examples: [
      "Start a new session for me.",
      "Start a session with sessionID {your session id}.",
    ],
  },
  {
    tool: "fetch_report",
    summary:
      "Fetch SEC data. Structured statement tables land in Files; the full annual report is ingested for RAG Q&A.",
    examples: [
      "Fetch full 10k 2023 report of AAPL.",
      "Fetch financials of Costco.",
    ],
  },
  {
    tool: "run_detailed_analysis",
    summary:
      "Build a curated 5-year income, balance, and cash flow report, then follow next_actions: ingest the full 10-K and pin four narrative sections onto Detailed Analysis.",
    examples: ["Do detailed analysis of Micron."],
  },
  {
    tool: "create_dcf_model",
    summary:
      "Create a DCF template on the dashboard. Your assistant should ask forecast years (1–10); you fill assumptions in the editor.",
    examples: ["Build a 5 year dcf model for MU."],
  },
  {
    tool: "run_comparative_analysis",
    summary: "Peer comparison for a target company and 1–5 peers. Results appear in Models.",
    examples: ["Compare apple, microsoft and google using run_comparative_analysis."],
  },
  {
    tool: "query_rag",
    summary:
      "Ask questions against an ingested 10-K. Your assistant retrieves sections, may loop for more context, then answers.",
    examples: ["What are the main risks in NVIDIA's latest 10-K?"],
  },
  {
    tool: "rag_res_on_display",
    summary:
      "Pin a formatted answer to RAG Results (default), or to a Detailed Analysis narrative section when destination=detailed_analysis with ticker and section_key.",
    examples: [
      "Pin last output on dashboard.",
      "Pin gross profit narrative to detailed analysis for AAPL.",
    ],
  },
];

export const MCP_TOOL_GUIDE_EXAMPLE_NOTE =
  "Specifying the tool name isn't necessary, but it helps the LLM use the right tool.";
