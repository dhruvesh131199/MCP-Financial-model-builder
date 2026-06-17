import { useState } from "react";
import { Link } from "react-router-dom";
import SegmentedToggle from "../components/setup/SegmentedToggle";
import ClaudeMacGuide from "../components/setup/guides/ClaudeMacGuide";
import PlaceholderGuide from "../components/setup/guides/PlaceholderGuide";

type OsChoice = "mac" | "windows";
type ClientChoice = "claude" | "cursor";

export default function SetupPage() {
  const [os, setOs] = useState<OsChoice>("mac");
  const [client, setClient] = useState<ClientChoice>("claude");

  const showClaudeMac = os === "mac" && client === "claude";

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
            Add a connector in Claude Settings, restart the app, and start building DCF models on
            your own private dashboard.
          </p>
        </header>

        <div className="mt-8 flex flex-wrap gap-6">
          <SegmentedToggle
            label="Your system"
            options={[
              { value: "mac", label: "Mac" },
              { value: "windows", label: "Windows" },
            ]}
            value={os}
            onChange={setOs}
          />
          <SegmentedToggle
            label="Your assistant"
            options={[
              { value: "claude", label: "Claude" },
              { value: "cursor", label: "Cursor" },
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
            <span className="font-normal text-gray-400"> · </span>
            {os === "mac" ? "macOS" : "Windows"}
          </h2>

          {showClaudeMac ? (
            <ClaudeMacGuide />
          ) : (
            <PlaceholderGuide os={os} client={client} />
          )}
        </section>
      </div>
    </div>
  );
}
