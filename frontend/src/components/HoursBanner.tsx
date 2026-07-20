import { HOURS_BANNER_TEXT } from "../config/branding";

/** Top-of-app notice that backend hours are limited to daytime Eastern Time. */
export default function HoursBanner() {
  return (
    <div
      role="status"
      className="shrink-0 border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-sm text-amber-950"
    >
      {HOURS_BANNER_TEXT}
    </div>
  );
}
