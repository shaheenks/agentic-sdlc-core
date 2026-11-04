"use client";

// Connections page (version-01 M6): users connect their own accounts with a personal access token.
// Talks to the MCP server's /connections/ API, same origin through oauth2-proxy (the proxy adds the
// user's Entra token). The token typed here goes only to that API: it is never stored in the
// browser, never sent back, never shown again. Never paste a token into the chat.
//
// Layout (version-02 chat UX): one compact row per connection (name, provider, status chip,
// account and expiry, actions). The token form opens on Connect / Replace; the provider's token
// instructions sit in a collapsible panel inside it. Disconnect asks inline first.

import { type FormEvent, useCallback, useEffect, useState } from "react";

import { CONNECTIONS_CHANGED, UserStatus } from "@/components/UserStatus";
import { statusChip } from "@/lib/status";

type Connection = {
  id: string;
  provider: string;
  edition: string;
  description: string;
  token_help: string;
  needs_username: boolean;
  max_token_days: number;
  connected: boolean;
  display?: string;
  account?: string;
  username?: string | null;
  expires_at?: string | null;
  status?: string;
  expired?: boolean;
  expiring_soon?: boolean;
};

const API = "/connections/";
const WRITE_HEADERS = { "Content-Type": "application/json", "X-SDLC-Connections": "1" };

function isoDay(offset: number): string {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
}

async function detail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : `request failed (${response.status})`;
  } catch {
    return `request failed (${response.status})`;
  }
}

type Mode = "idle" | "form" | "confirm-disconnect";

function ConnectionRow({ c, onChange }: { c: Connection; onChange: () => void }) {
  const [mode, setMode] = useState<Mode>("idle");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chip = statusChip(c);

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError(null);
    const response = await fetch(`${API}${encodeURIComponent(c.id)}`, {
      method: "PUT",
      headers: WRITE_HEADERS,
      body: JSON.stringify({
        token: String(data.get("token") ?? ""),
        username: c.needs_username ? String(data.get("username") ?? "") : undefined,
        expires_at: String(data.get("expires_at") ?? "") || undefined,
      }),
    });
    form.reset(); // the token leaves the page either way
    setBusy(false);
    if (!response.ok) setError(await detail(response));
    else {
      setMode("idle");
      onChange();
    }
  }

  async function disconnect() {
    setBusy(true);
    setError(null);
    const response = await fetch(`${API}${encodeURIComponent(c.id)}`, {
      method: "DELETE",
      headers: WRITE_HEADERS,
    });
    setBusy(false);
    setMode("idle");
    if (!response.ok) setError(await detail(response));
    else onChange();
  }

  return (
    <section className="conn-row">
      <div className="conn-head">
        <div className="conn-name">
          <span className="conn-title">{c.description || c.id}</span>
          <span className="chip">
            {c.provider} · {c.edition}
          </span>
          <span className={`status-chip status-${chip.state}`}>{chip.label}</span>
        </div>
        <div className="conn-buttons">
          {mode === "idle" && (
            <>
              <button type="button" onClick={() => setMode("form")} disabled={busy}>
                {c.connected ? "Replace" : "Connect"}
              </button>
              {c.connected && (
                <button type="button" onClick={() => setMode("confirm-disconnect")} disabled={busy}>
                  Disconnect
                </button>
              )}
            </>
          )}
        </div>
      </div>
      {chip.detail && <div className="conn-sub">{chip.detail}</div>}

      {mode === "confirm-disconnect" && (
        <div className="conn-confirm">
          <span>
            Remove this token here? Revoke it at {c.provider} too if you no longer need it.
          </span>
          <span className="conn-buttons">
            <button type="button" className="danger" onClick={disconnect} disabled={busy} autoFocus>
              Disconnect
            </button>
            <button type="button" onClick={() => setMode("idle")} disabled={busy}>
              Cancel
            </button>
          </span>
        </div>
      )}

      {mode === "form" && (
        <form className="conn-form" onSubmit={connect} autoComplete="off">
          <div className="conn-fields">
            {c.needs_username && (
              <label>
                Account email
                <input name="username" type="email" required defaultValue={c.username ?? ""} />
              </label>
            )}
            <label>
              Personal access token
              <input name="token" type="password" required autoComplete="off" spellCheck={false} autoFocus />
            </label>
            <label>
              Expires on
              <input
                name="expires_at"
                type="date"
                min={isoDay(0)}
                max={isoDay(c.max_token_days)}
                required={c.provider !== "github"}
              />
            </label>
          </div>
          {c.token_help && (
            <details className="conn-help">
              <summary>How to create this token</summary>
              <p>{c.token_help}</p>
            </details>
          )}
          <div className="conn-buttons">
            <button type="submit" className="primary" disabled={busy}>
              {c.connected ? "Save new token" : "Connect"}
            </button>
            <button type="button" onClick={() => setMode("idle")} disabled={busy}>
              Cancel
            </button>
          </div>
        </form>
      )}
      {error && <div className="conn-error">{error}</div>}
    </section>
  );
}

export default function ConnectionsPage() {
  const [items, setItems] = useState<Connection[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const response = await fetch(API, { headers: { Accept: "application/json" } });
    if (!response.ok) {
      setError(await detail(response));
      return;
    }
    setError(null);
    setItems((await response.json()).connections);
    window.dispatchEvent(new Event(CONNECTIONS_CHANGED)); // navbar status follows connect/disconnect
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <main className="shell">
      <header className="topbar">
        <span className="brand">SDLC Assistant</span>
        <nav>
          <a href="/chat/">Chat</a>
          <UserStatus />
        </nav>
      </header>
      <div className="page conn-page">
        <h1 className="page-title">Connections</h1>
        <p className="conn-about">
          Read Jira, Confluence, GitHub and Bitbucket with your own permissions, using a personal access token you
          create. Tokens are stored encrypted for you only and never shown again. Never paste a token into the chat.
        </p>
        {error && <div className="conn-error">{error}</div>}
        {items === null && !error && <div className="tool pending">Loading…</div>}
        <div className="conn-list-page">
          {items?.map((c) => <ConnectionRow key={c.id} c={c} onChange={load} />)}
        </div>
      </div>
    </main>
  );
}
