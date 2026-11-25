"use client";

import { useCallback, useEffect, useState } from "react";

import { api, formatWhen } from "@/lib/client";
import { type Check, describeCheck, type Provider } from "@/lib/connections";

type Connection = { provider: string; account?: string | null; saved_at?: string; status?: string };
type Listing = { connections: Connection[]; providers: Record<string, Provider> };

// The user's own connections to downstream systems (FR-CONN-001). Tokens are entered on each provider's page,
// never in a chat; "Test" signs in with the stored token and says as whom.
export default function ConnectionsPage() {
  const [listing, setListing] = useState<Listing | null>(null);
  const [checks, setChecks] = useState<Record<string, Check | "testing">>({});
  const [error, setError] = useState("");
  const refresh = useCallback(() => {
    api<Listing>("/api/connections").then(setListing, (e: Error) => setError(e.message));
  }, []);
  useEffect(refresh, [refresh]);

  const revoke = async (provider: string) => {
    if (!window.confirm(`Remove your ${provider} connection? It stops being used at once.`)) return;
    await api(`/api/connections/${provider}`, { method: "DELETE" }).catch((e: Error) => setError(e.message));
    setChecks(({ [provider]: _, ...rest }) => rest);
    refresh();
  };

  const test = async (provider: string) => {
    setChecks((c) => ({ ...c, [provider]: "testing" }));
    try {
      const result = await api<Check>(`/api/connections/${provider}/test`, { method: "POST" });
      setChecks((c) => ({ ...c, [provider]: result }));
    } catch (e) {
      setChecks((c) => ({ ...c, [provider]: { status: "refused", reason: (e as Error).message } }));
    }
  };

  return (
    <main className="page">
      <h1>Connections</h1>
      <p className="hint">
        Your own tokens for the systems the agents work with as you. They are checked when you save them, stored
        encrypted and never shown again.
      </p>
      {error && <p className="error">{error}</p>}
      {listing === null ? (
        <p>Loading…</p>
      ) : (
        <ul className="list">
          {Object.entries(listing.providers).map(([id, provider]) => {
            const mine = listing.connections.find((c) => c.provider === id);
            const check = checks[id];
            return (
              <li key={id}>
                <span>
                  <strong>{provider.name}</strong>
                  <small>
                    {mine
                      ? ` connected${mine.account ? ` as ${mine.account}` : ""}${mine.saved_at ? ` · ${formatWhen(mine.saved_at)}` : ""}`
                      : " not connected"}
                  </small>
                  {check && (
                    <small className={`check ${check === "testing" ? "" : `check-${check.status}`}`} role="status">
                      {check === "testing" ? "Testing…" : describeCheck(check)}
                    </small>
                  )}
                </span>
                <span className="actions">
                  {mine && (
                    <button type="button" className="link" onClick={() => test(id)} disabled={check === "testing"}>
                      Test
                    </button>
                  )}
                  <a href={`/connections/${id}`}>{mine ? "Replace" : "Connect"}</a>
                  {mine && (
                    <button type="button" className="link danger" onClick={() => revoke(id)}>
                      Remove
                    </button>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
