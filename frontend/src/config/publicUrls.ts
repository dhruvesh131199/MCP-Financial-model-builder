/** Production URLs — override with VITE_* at Render build time. */
export const PUBLIC_APP_URL =
  import.meta.env.VITE_APP_URL ?? "https://mcp-financial-model-builder.onrender.com";

export const PUBLIC_API_URL =
  import.meta.env.VITE_API_URL ?? "https://myfmdc-api.duckdns.org";

export const PUBLIC_MCP_URL =
  import.meta.env.VITE_PUBLIC_MCP_URL ?? "https://myfmdc-mcp.duckdns.org/mcp";
