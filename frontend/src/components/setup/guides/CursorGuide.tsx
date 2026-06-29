import {
  MCP_CONFIG_KEY,
  MCP_SAMPLE_TOOLS,
  MCP_SUGGESTED_NAME,
} from "../../../config/branding";
import { PUBLIC_APP_URL, PUBLIC_MCP_URL } from "../../../config/publicUrls";
import SetupImage from "../SetupImage";

const MCP_CONFIG = `{
  "mcpServers": {
    "${MCP_CONFIG_KEY}": {
      "url": "${PUBLIC_MCP_URL}"
    }
  }
}`;

export default function CursorGuide() {
  return (
    <div className="space-y-8">
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
        <strong>About 1 minute</strong> — add one MCP server in Cursor settings, restart, and
        you&apos;re ready. Same steps on Mac and Windows.
      </div>

      <ol className="space-y-8">
        <li className="space-y-3">
          <div className="flex gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gray-900 text-xs font-semibold text-white">
              1
            </span>
            <div className="min-w-0 space-y-2">
              <h3 className="font-medium text-gray-900">Open MCP settings</h3>
              <p className="text-sm text-gray-600">
                In Cursor, go to <strong>Settings</strong> → <strong>Tools &amp; MCP</strong> →{" "}
                <strong>Add new MCP server</strong> (or edit <code className="rounded bg-gray-100 px-1 text-xs">mcp.json</code>).
              </p>
            </div>
          </div>
          <SetupImage
            src="/setup/cursor/step-1-mcp-settings.png"
            alt="Cursor Settings showing Tools and MCP with Add new MCP server"
            caption="Settings → Tools & MCP"
          />
        </li>

        <li className="space-y-3">
          <div className="flex gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gray-900 text-xs font-semibold text-white">
              2
            </span>
            <div className="min-w-0 space-y-2">
              <h3 className="font-medium text-gray-900">Paste this config</h3>
              <p className="text-sm text-gray-600">
                Pick any server name you like — we suggest <strong>{MCP_SUGGESTED_NAME}</strong>{" "}
                (config key <code className="rounded bg-gray-100 px-1 text-xs">{MCP_CONFIG_KEY}</code>
                ). If Cursor only asks for a URL, paste just the{" "}
                <code className="rounded bg-gray-100 px-1 text-xs">url</code> line below.
              </p>
              <pre className="overflow-x-auto rounded-lg bg-gray-900 px-4 py-3 text-sm text-gray-100">
                <code>{MCP_CONFIG}</code>
              </pre>
            </div>
          </div>
          <SetupImage
            src="/setup/cursor/step-2-config.png"
            alt="Cursor MCP config with financial workflow URL"
            caption="Paste the MCP config"
          />
        </li>

        <li className="space-y-3">
          <div className="flex gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gray-900 text-xs font-semibold text-white">
              3
            </span>
            <div className="min-w-0 space-y-2">
              <h3 className="font-medium text-gray-900">Restart Cursor</h3>
              <p className="text-sm text-gray-600">
                Fully quit and reopen Cursor so the MCP server loads.
              </p>
            </div>
          </div>
          <SetupImage
            src="/setup/cursor/step-3-restart.png"
            alt="Restarting Cursor after adding MCP config"
            caption="Quit Cursor completely, then reopen"
          />
        </li>

        <li className="space-y-3">
          <div className="flex gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gray-900 text-xs font-semibold text-white">
              4
            </span>
            <div className="min-w-0 space-y-2">
              <h3 className="font-medium text-gray-900">Enable tools in chat</h3>
              <p className="text-sm text-gray-600">
                In <strong>Settings → Tools &amp; MCP</strong>, your server should show as connected.
                Start a <strong>new chat</strong> and make sure the MCP server is toggled on for that
                chat (under Tools or the MCP panel). You should see tools like{" "}
                {MCP_SAMPLE_TOOLS.map((t, i) => (
                  <span key={t}>
                    {i > 0 ? ", " : ""}
                    <code className="rounded bg-gray-100 px-1 text-xs">{t}</code>
                  </span>
                ))}
                .
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
            src="/setup/cursor/step-4-tools-live.png"
            alt="Cursor MCP settings showing server connected and tools in chat"
            caption="Connected — then try start_session in a new chat"
          />
        </li>
      </ol>
    </div>
  );
}
