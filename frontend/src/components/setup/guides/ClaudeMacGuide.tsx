import { PUBLIC_APP_URL, PUBLIC_MCP_URL } from "../../../config/publicUrls";
import SetupImage from "../SetupImage";

export default function ClaudeMacGuide() {
  return (
    <div className="space-y-8">
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
        <strong>About 1 minute</strong> — add a connector in Settings, restart Claude, and
        you&apos;re ready to go.
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
                Open <strong>Claude</strong> → <strong>Settings</strong>, go to{" "}
                <strong>Connectors</strong>, and add a custom connector.
              </p>
              <p className="text-sm text-gray-600">Paste this URL:</p>
              <pre className="overflow-x-auto rounded-lg bg-gray-900 px-4 py-3 text-sm text-gray-100">
                <code>{PUBLIC_MCP_URL}</code>
              </pre>
              <p className="text-sm text-gray-600">
                Name it <strong>Financial Models</strong>.
              </p>
            </div>
          </div>
          <SetupImage
            src="/setup/claude-mac/step-1-settings.png"
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
                Fully quit Claude with <kbd className="rounded border px-1">Cmd</kbd> +{" "}
                <kbd className="rounded border px-1">Q</kbd>, then open it again. Closing the
                window isn&apos;t enough — you need a full restart for the connector to load.
              </p>
            </div>
          </div>
          <SetupImage
            src="/setup/claude-mac/step-2-restart.png"
            alt="Quitting Claude Desktop from the menu bar"
            caption="Quit Claude completely, then reopen"
          />
        </li>

        <li className="space-y-3">
          <div className="flex gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gray-900 text-xs font-semibold text-white">
              3
            </span>
            <div className="min-w-0 space-y-2">
              <h3 className="font-medium text-gray-900">Turn on Financial Models in chat</h3>
              <p className="text-sm text-gray-600">
                Start a new chat. Tap the <strong>+</strong> button, then{" "}
                <strong>Connectors</strong> → <strong>Financial Models</strong>.
              </p>
            </div>
          </div>
          <SetupImage
            src="/setup/claude-mac/step-3-connectors.png"
            alt="Claude chat plus menu showing Connectors and Financial Models"
            caption="+ → Connectors → Financial Models"
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
                Ask Claude to start a session. You&apos;ll get a private link on our dashboard —
                open it and keep chatting. Models show up as you build them.
              </p>
              <blockquote className="rounded-lg border border-[var(--border-soft)] bg-[var(--bg-sidebar)] px-4 py-3 text-sm italic text-gray-700">
                Call start_session and give me my dashboard link.
              </blockquote>
              <p className="text-xs text-gray-500">
                Your dashboard lives at{" "}
                <a
                  href={PUBLIC_APP_URL}
                  className="font-medium text-gray-700 underline"
                  target="_blank"
                  rel="noreferrer"
                >
                  {PUBLIC_APP_URL}
                </a>
                . Setup guide:{" "}
                <a
                  href={`${PUBLIC_APP_URL}/setup`}
                  className="font-medium text-gray-700 underline"
                  target="_blank"
                  rel="noreferrer"
                >
                  /setup
                </a>
              </p>
            </div>
          </div>
          <SetupImage
            src="/setup/claude-mac/step-4-dashboard.png"
            alt="Browser dashboard showing a DCF model after chatting with Claude"
            caption="Your private dashboard link"
          />
        </li>
      </ol>
    </div>
  );
}
