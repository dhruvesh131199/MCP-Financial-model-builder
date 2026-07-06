/** Production URLs — set VITE_* on Render; VIEW_BASE_URL on EC2 must match VITE_APP_URL exactly. */
export const PUBLIC_APP_URL =
  import.meta.env.VITE_APP_URL ?? "https://finsight-mcp-app.onrender.com";

export const PUBLIC_API_URL =
  import.meta.env.VITE_API_URL ?? "https://myfmdc-api.duckdns.org";

export const PUBLIC_MCP_URL =
  import.meta.env.VITE_PUBLIC_MCP_URL ?? "https://myfmdc-mcp.duckdns.org/mcp";
