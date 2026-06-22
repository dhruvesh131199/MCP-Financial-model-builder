/// <reference types="vite/client" />
/// <reference types="vitest/globals" />

interface ImportMetaEnv {
  readonly VITE_APP_URL?: string;
  readonly VITE_API_URL?: string;
  readonly VITE_PUBLIC_MCP_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
