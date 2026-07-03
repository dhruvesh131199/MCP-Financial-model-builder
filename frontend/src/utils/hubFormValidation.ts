/** Shared copy and styles for dashboard hub forms (Models, Fetch Financials). */

export const FILL_REQUIRED_MSG = "Please fill all required values.";

export function inputFieldClass(hasError: boolean, extra = ""): string {
  const border = hasError
    ? "border-red-400 ring-1 ring-red-200 focus:border-red-500 focus:ring-red-200"
    : "border-gray-200";
  return `rounded-lg border px-3 py-2 text-sm ${border} ${extra}`.trim();
}

export function chipFieldClass(hasError: boolean, disabled: boolean): string {
  if (disabled) {
    return `flex min-h-[42px] flex-wrap items-center gap-1.5 rounded-lg border bg-white px-2 py-1.5 opacity-60 ${
      hasError ? "border-red-400 ring-1 ring-red-200" : "border-gray-200"
    }`;
  }
  if (hasError) {
    return "flex min-h-[42px] flex-wrap items-center gap-1.5 rounded-lg border border-red-400 bg-white px-2 py-1.5 ring-1 ring-red-200 focus-within:border-red-500 focus-within:ring-red-200";
  }
  return "flex min-h-[42px] flex-wrap items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-2 py-1.5 focus-within:border-indigo-400 focus-within:ring-1 focus-within:ring-indigo-200";
}
