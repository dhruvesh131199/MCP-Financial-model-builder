/** URLs from Vite env — local: `.env.development`; Render: dashboard env vars at build time. */

type ViteUrlKey = "VITE_API_URL" | "VITE_PUBLIC_MCP_URL";

function requireViteEnv(key: ViteUrlKey): string {
  const value = import.meta.env[key]?.trim();
  if (!value) {
    throw new Error(
      `Missing ${key}. ` +
        "Local: use frontend/.env.development (or .env.local). " +
        "Render: set in dashboard and redeploy.",
    );
  }
  return value.replace(/\/$/, "");
}

/** Dashboard URL for MCP setup copy — same origin as the running app (no Render env needed). */
export function appUrl(): string {
  return window.location.origin;
}

export const PUBLIC_API_URL = requireViteEnv("VITE_API_URL");
export const PUBLIC_MCP_URL = requireViteEnv("VITE_PUBLIC_MCP_URL");
