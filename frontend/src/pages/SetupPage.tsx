import { useState } from "react";
import { Link } from "react-router-dom";
import SegmentedToggle from "../components/setup/SegmentedToggle";
import ClaudeGuide from "../components/setup/guides/ClaudeGuide";
import CursorGuide from "../components/setup/guides/CursorGuide";

type ClientChoice = "claude" | "cursor";

export default function SetupPage() {
  const [client, setClient] = useState<ClientChoice>("cursor");

  return (
    <div className="min-h-screen bg-[var(--bg-app)] px-4 py-10">
      <div className="mx-auto max-w-2xl">
        <Link
          to="/"
          className="inline-flex items-center gap-1 text-sm text-gray-500 transition-colors hover:text-gray-900"
        >
          <span aria-hidden>←</span> Back
        </Link>

        <header className="mt-4">
          <h1 className="text-3xl font-semibold tracking-tight text-gray-900">Set up in 1 minute</h1>
          <p className="mt-2 text-gray-600">
            Add our MCP server to Cursor or Claude, restart once, and start building DCF models on
            your private dashboard.
          </p>
        </header>

        <div className="mt-8">
          <SegmentedToggle
            label="Your assistant"
            options={[
              { value: "cursor", label: "Cursor" },
              { value: "claude", label: "Claude" },
            ]}
            value={client}
            onChange={setClient}
          />
        </div>

        <section
          className="mt-8 rounded-2xl border border-[var(--border-soft)] bg-white p-6 shadow-sm sm:p-8"
          aria-live="polite"
        >
          <h2 className="mb-6 text-lg font-semibold text-gray-900">
            {client === "claude" ? "Claude Desktop" : "Cursor"}
          </h2>

          {client === "cursor" ? <CursorGuide /> : <ClaudeGuide />}
        </section>
      </div>
    </div>
  );
}
