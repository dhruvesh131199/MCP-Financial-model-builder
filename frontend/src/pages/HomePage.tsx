import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createSession } from "../api";
import {
  HOME_EXPLORE_DESCRIPTION,
  HOME_EXPLORE_TITLE,
  HOME_MCP_DESCRIPTION,
  HOME_MCP_TITLE,
  HOME_TAGLINE,
  PRODUCT_TITLE,
} from "../config/branding";

export default function HomePage() {
  const navigate = useNavigate();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStartExploring() {
    setStarting(true);
    setError(null);
    try {
      const { session_id } = await createSession();
      navigate(`/s/${session_id}`);
    } catch {
      setError("Could not start a session. Is the API running and VIEW_BASE_URL set on EC2?");
      setStarting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg-app)] px-4 py-12 sm:py-16">
      <div className="mx-auto max-w-xl">
        <header className="text-center">
          <h1 className="text-3xl font-semibold tracking-tight text-gray-900 sm:text-4xl">
            {PRODUCT_TITLE}
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-gray-600 sm:text-base">{HOME_TAGLINE}</p>
        </header>

        <section className="mt-10 rounded-2xl border border-[var(--border-soft)] bg-white p-6 shadow-sm sm:p-8">
          <h2 className="text-lg font-semibold text-gray-900">{HOME_MCP_TITLE}</h2>
          <p className="mt-2 text-sm leading-relaxed text-gray-600">{HOME_MCP_DESCRIPTION}</p>
          <Link
            to="/setup"
            className="mt-5 flex w-full items-center justify-center rounded-xl bg-gray-900 px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-gray-800"
          >
            Set up in 1 minute →
          </Link>
        </section>

        <div className="my-8 flex items-center gap-4">
          <div className="h-px flex-1 bg-gray-200" aria-hidden />
          <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">or</span>
          <div className="h-px flex-1 bg-gray-200" aria-hidden />
        </div>

        <section className="rounded-2xl border border-indigo-200/80 bg-gradient-to-br from-indigo-50/60 to-white p-6 shadow-sm sm:p-8">
          <h2 className="text-lg font-semibold text-gray-900">{HOME_EXPLORE_TITLE}</h2>
          <p className="mt-2 text-sm leading-relaxed text-gray-600">{HOME_EXPLORE_DESCRIPTION}</p>
          <button
            type="button"
            onClick={() => void handleStartExploring()}
            disabled={starting}
            className="mt-5 flex w-full items-center justify-center rounded-xl border border-indigo-300 bg-white px-4 py-3 text-sm font-medium text-indigo-700 shadow-sm transition-colors hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {starting ? "Starting…" : "Start exploring →"}
          </button>
          {error ? (
            <p className="mt-3 text-center text-xs text-red-600" role="alert">
              {error}
            </p>
          ) : null}
        </section>

        <p className="mt-8 text-center text-xs text-gray-400">
          Demo mode: security is the unguessable session URL (like a Google Docs link).
        </p>
      </div>
    </div>
  );
}
