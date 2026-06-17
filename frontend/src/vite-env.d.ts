/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PUBLIC_MCP_URL?: string;
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
