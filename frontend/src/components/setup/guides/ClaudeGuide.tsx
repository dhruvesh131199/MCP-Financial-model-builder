import { MCP_SUGGESTED_NAME } from "../../../config/branding";
import { PUBLIC_APP_URL, PUBLIC_MCP_URL } from "../../../config/publicUrls";
import SetupImage from "../SetupImage";

export default function ClaudeGuide() {
  return (
    <div className="space-y-8">
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
        <strong>About 1 minute</strong> — add a connector in Settings, restart Claude, and
        you&apos;re ready. Same steps on Mac and Windows.
      </div>

      <ol className="space-y-8">
        <li className="space-y-3">
          <div className="flex gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gray-900 text-xs font-semibold text-white">
              1
            </span>
            <div className="min-w-0 space-y-2">
              <h3 className="font-medium text-gray-900">Add the connector in Settings</h3>
              <p className="text-sm text-gray-600">
                Open <strong>Claude Desktop</strong> → <strong>Settings</strong>, go to{" "}
                <strong>Connectors</strong> (or <strong>Developer</strong> → MCP), and add a custom
                connector.
              </p>
              <p className="text-sm text-gray-600">Paste this URL:</p>
              <pre className="overflow-x-auto rounded-lg bg-gray-900 px-4 py-3 text-sm text-gray-100">
                <code>{PUBLIC_MCP_URL}</code>
              </pre>
              <p className="text-sm text-gray-600">
                Name it anything you&apos;ll recognize — e.g. <strong>{MCP_SUGGESTED_NAME}</strong>.
              </p>
            </div>
          </div>
          <SetupImage
            src="/setup/claude/step-1-settings.png"
            alt="Claude Desktop Settings with Connectors and a custom connector URL"
            caption="Settings → Connectors → add custom connector"
          />
        </li>

        <li className="space-y-3">
          <div className="flex gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gray-900 text-xs font-semibold text-white">
              2
            </span>
            <div className="min-w-0 space-y-2">
              <h3 className="font-medium text-gray-900">Restart Claude</h3>
              <p className="text-sm text-gray-600">
                Fully quit and reopen Claude Desktop — closing the window isn&apos;t enough.
              </p>
            </div>
          </div>
          <SetupImage
            src="/setup/claude/step-2-restart.png"
            alt="Quitting Claude Desktop"
            caption="Quit Claude completely, then reopen"
          />
        </li>

        <li className="space-y-3">
          <div className="flex gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gray-900 text-xs font-semibold text-white">
              3
            </span>
            <div className="min-w-0 space-y-2">
              <h3 className="font-medium text-gray-900">Turn on the connector in chat</h3>
              <p className="text-sm text-gray-600">
                Start a <strong>new chat</strong>. Tap the <strong>+</strong> button (or the tools
                menu), then <strong>Connectors</strong> → enable{" "}
                <strong>{MCP_SUGGESTED_NAME}</strong> (or whatever you named it).
              </p>
            </div>
          </div>
          <SetupImage
            src="/setup/claude/step-3-connectors.png"
            alt="Claude chat plus menu showing Connectors and Financial Workflow"
            caption="+ → Connectors → enable your workflow server"
          />
        </li>

        <li className="space-y-3">
          <div className="flex gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gray-900 text-xs font-semibold text-white">
              4
            </span>
            <div className="min-w-0 space-y-2">
              <h3 className="font-medium text-gray-900">Get your private dashboard</h3>
              <p className="text-sm text-gray-600">
                Ask Claude to start a session. Open the link it gives you — filings, models, and
                reports from chat will appear on the dashboard as you work.
              </p>
              <blockquote className="rounded-lg border border-[var(--border-soft)] bg-[var(--bg-sidebar)] px-4 py-3 text-sm italic text-gray-700">
                Call start_session and give me my dashboard link.
              </blockquote>
              <p className="text-xs text-gray-500">
                Dashboard:{" "}
                <a
                  href={PUBLIC_APP_URL}
                  className="font-medium text-gray-700 underline"
                  target="_blank"
                  rel="noreferrer"
                >
                  {PUBLIC_APP_URL}
                </a>
              </p>
            </div>
          </div>
          <SetupImage
            src="/setup/claude/step-4-dashboard.png"
            alt="Browser dashboard showing workspace content after chatting with Claude"
            caption="Your private analyzer workspace"
          />
        </li>
      </ol>
    </div>
  );
}
