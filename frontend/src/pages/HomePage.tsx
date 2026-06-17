export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[var(--bg-app)] px-4">
      <div className="max-w-lg rounded-2xl border border-[var(--border-soft)] bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-semibold text-gray-900">Financial Model Builder</h1>
        <p className="mt-2 text-sm text-gray-600">
          Build DCF models in Cursor or Claude. Each user gets a private workspace link —
          no signup required.
        </p>

        <ol className="mt-6 list-decimal space-y-2 pl-5 text-sm text-gray-700">
          <li>
            Add the MCP server to Cursor:{" "}
            <code className="rounded bg-gray-100 px-1 text-xs">
              http://localhost:8080/mcp
            </code>
          </li>
          <li>Ask Cursor to call <strong>start_session</strong> — it gives you a private link</li>
          <li>Open that link and keep chatting — your model appears on the dashboard</li>
        </ol>

        <p className="mt-6 text-xs text-gray-400">
          Demo mode: security is the unguessable session URL (like a Google Docs link).
        </p>
      </div>
    </div>
  );
}
