import { Link } from "react-router-dom";
import { HOME_TAGLINE, PRODUCT_TITLE } from "../config/branding";

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[var(--bg-app)] px-4">
      <div className="max-w-lg rounded-2xl border border-[var(--border-soft)] bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-semibold text-gray-900">{PRODUCT_TITLE}</h1>
        <p className="mt-2 text-sm text-gray-600">{HOME_TAGLINE}</p>

        <Link
          to="/setup"
          className="mt-6 flex w-full items-center justify-center rounded-xl bg-gray-900 px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-gray-800"
        >
          Set up in 1 minute →
        </Link>

        <p className="mt-6 text-xs text-gray-400">
          Demo mode: security is the unguessable session URL (like a Google Docs link).
        </p>
      </div>
    </div>
  );
}
