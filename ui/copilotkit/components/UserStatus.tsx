"use client";

// Navbar user status (version-02 chat UX): initials + name, and a dot per personal access token
// connection (green connected, amber expiring/expired/rejected, grey not connected). The panel
// lists each connection and links to the Connections page. Data comes from GET /me (agent) and
// GET /connections/ (MCP server), same origin through oauth2-proxy; no token reaches this code.

import { useCallback, useEffect, useState } from "react";

import {
  type ConnectionStatus,
  connectionStatuses,
  initials,
  type Me,
  overallState,
  parseMe,
} from "@/lib/status";

/** Fired by the Connections page after a load, connect or disconnect. */
export const CONNECTIONS_CHANGED = "sdlc:connections-changed";

async function getJson(url: string): Promise<unknown | null> {
  try {
    const response = await fetch(url, { headers: { Accept: "application/json" }, cache: "no-store" });
    return response.ok ? await response.json() : null; // 401/503: show nothing rather than guess
  } catch {
    return null;
  }
}

export function UserStatus() {
  const [me, setMe] = useState<Me | null>(null);
  const [connections, setConnections] = useState<ConnectionStatus[]>([]);
  const [open, setOpen] = useState(false);

  const load = useCallback(async () => {
    const [meBody, connBody] = await Promise.all([getJson("/me"), getJson("/connections/")]);
    setMe(parseMe(meBody));
    setConnections(connectionStatuses(connBody));
  }, []);

  useEffect(() => {
    void load();
    const refresh = () => document.visibilityState === "visible" && void load();
    const reload = () => void load();
    window.addEventListener("focus", refresh);
    window.addEventListener(CONNECTIONS_CHANGED, reload);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      window.removeEventListener("focus", refresh);
      window.removeEventListener(CONNECTIONS_CHANGED, reload);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [load]);

  if (!me) return null;
  const state = overallState(connections);

  return (
    <div className="user">
      <button
        type="button"
        className="user-button"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((v) => !v)}
        title={me.upn}
      >
        <span className="avatar" aria-hidden="true">
          {initials(me)}
          {state && <span className={`dot dot-${state} avatar-dot`} />}
        </span>
        <span className="user-name">{me.name || me.upn}</span>
      </button>
      {open && (
        <div className="user-panel" role="dialog" aria-label="Your account">
          <div className="user-panel-head">
            <div className="user-panel-name">{me.name}</div>
            {me.upn && <div className="user-panel-upn">{me.upn}</div>}
          </div>
          {connections.length > 0 && (
            <ul className="conn-list">
              {connections.map((c) => (
                <li key={c.id}>
                  <span className={`dot dot-${c.state}`} aria-hidden="true" />
                  <span className="conn-label">{c.label}</span>
                  <span className="conn-detail">{c.detail}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="user-panel-links">
            <a href="/chat/connections">Manage connections</a>
            <a href="/oauth2/sign_out">Sign out</a>
          </div>
        </div>
      )}
    </div>
  );
}
