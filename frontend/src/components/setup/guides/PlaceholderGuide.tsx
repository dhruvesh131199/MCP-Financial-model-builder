type PlaceholderGuideProps = {
  os: "mac" | "windows";
  client: "claude" | "cursor";
};

const CLIENT_LABELS = {
  claude: "Claude Desktop",
  cursor: "Cursor",
} as const;

const OS_LABELS = {
  mac: "macOS",
  windows: "Windows",
} as const;

export default function PlaceholderGuide({ os, client }: PlaceholderGuideProps) {
  return (
    <div className="flex min-h-48 flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border-soft)] bg-[var(--bg-sidebar)] px-6 py-12 text-center">
      <p className="text-sm font-medium text-gray-700">
        {CLIENT_LABELS[client]} on {OS_LABELS[os]} — coming soon
      </p>
      <p className="mt-2 max-w-sm text-sm text-gray-500">
        We&apos;re writing this guide next. For now, switch to Claude + Mac above — that&apos;s the
        fastest path to get started.
      </p>
    </div>
  );
}
