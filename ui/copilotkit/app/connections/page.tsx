"use client";

// Connections page (version-01 M6): users connect their own accounts with a personal access token.
// Talks to the MCP server's /connections/ API, same origin through oauth2-proxy (the proxy adds the
// user's Entra token). The token typed here goes only to that API: it is never stored in the
// browser, never sent back, never shown again. Never paste a token into the chat.

import { type FormEvent, useCallback, useEffect, useState } from "react";

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

function ConnectionCard({ c, onChange }: { c: Connection; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    else onChange();
  }

  async function disconnect() {
    setBusy(true);
    setError(null);
    const response = await fetch(`${API}${encodeURIComponent(c.id)}`, {
      method: "DELETE",
      headers: WRITE_HEADERS,
    });
    setBusy(false);
    if (!response.ok) setError(await detail(response));
    else onChange();
  }

  const state = !c.connected
    ? "Not connected"
    : c.status === "invalid"
      ? "Token rejected by the provider: connect again"
      : c.expired
        ? "Token expired: connect again"
        : `Connected as ${c.display || c.account}`;
  const warn = c.connected && (c.status === "invalid" || c.expired || c.expiring_soon);

  return (
    <section className="tool connection">
      <div className="tool-title">
        {c.description || c.id} <span className="badge">{c.provider} · {c.edition}</span>
      </div>
      <div className={warn ? "conn-state warn" : "conn-state"}>
        {state}
        {c.connected && c.expires_at && <span> · expires {c.expires_at}</span>}
        {c.expiring_soon && !c.expired && <span> · expiring soon</span>}
      </div>
      {c.token_help && <p className="conn-help">{c.token_help}</p>}
      <form className="conn-form" onSubmit={connect} autoComplete="off">
        {c.needs_username && (
          <label>
            Account email
            <input name="username" type="email" required defaultValue={c.username ?? ""} />
          </label>
        )}
        <label>
          Personal access token
          <input name="token" type="password" required autoComplete="off" spellCheck={false} />
        </label>
        <label>
          Token expires on
          <input
            name="expires_at"
            type="date"
            min={isoDay(0)}
            max={isoDay(c.max_token_days)}
            required={c.provider !== "github"}
          />
        </label>
        <div className="conn-actions">
          <button type="submit" disabled={busy}>
            {c.connected ? "Replace token" : "Connect"}
          </button>
          {c.connected && (
            <button type="button" onClick={disconnect} disabled={busy}>
              Disconnect
            </button>
          )}
        </div>
      </form>
      {error && <div className="conn-error">{error}</div>}
      {c.connected && (
        <p className="conn-help">
          Disconnecting removes the token here; revoke it at {c.provider} too if you no longer need it.
        </p>
      )}
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
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <main className="shell">
      <header className="topbar">
        <span className="brand">Connections</span>
        <nav>
          <a href="/chat/">Chat</a>
          <a href="/oauth2/sign_out">Sign out</a>
        </nav>
      </header>
      <div className="page">
        <p className="conn-intro">
          Connect your own accounts so the assistant can read Jira, Confluence, GitHub and Bitbucket
          with <strong>your</strong> permissions. Tokens are stored encrypted for you only and are
          never shown again. Never paste a token into the chat.
        </p>
        {error && <div className="conn-error">{error}</div>}
        {items === null && !error && <div className="tool pending">Loading…</div>}
        {items?.map((c) => <ConnectionCard key={c.id} c={c} onChange={load} />)}
      </div>
    </main>
  );
}
