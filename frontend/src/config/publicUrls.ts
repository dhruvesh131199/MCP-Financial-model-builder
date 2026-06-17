/** Public HTTPS MCP endpoint — set VITE_PUBLIC_MCP_URL at build time when deployed. */
export const PUBLIC_MCP_URL =
  import.meta.env.VITE_PUBLIC_MCP_URL ?? "https://mcp.yourapp.com/mcp";
