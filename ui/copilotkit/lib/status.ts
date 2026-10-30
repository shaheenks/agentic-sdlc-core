// User status for the navbar (version-02 chat UX): who is signed in and the state of their
// personal access token connections. No React, no I/O: unit-tested in tests/status.test.ts.
//
// Sources (same origin, through oauth2-proxy, which adds the user's token server side):
// - GET /me            (agent): {name, upn} from the validated token, nothing else
// - GET /connections/  (MCP server): the Connections page's list; never contains tokens
// Display only: authorization happens in the MCP server.

export type Me = { name: string; upn: string };

export type ConnectionState = "ok" | "warn" | "off";

export type ConnectionStatus = {
  id: string;
  label: string;
  state: ConnectionState;
  detail: string; // e.g. "octo · expires 2026-12-01", "expires in 3 days", "not connected"
};

const str = (value: unknown): string => (typeof value === "string" ? value : "");

export function parseMe(body: unknown): Me | null {
  if (!body || typeof body !== "object") return null;
  const { name, upn } = body as Record<string, unknown>;
  const me = { name: str(name), upn: str(upn) };
  return me.name || me.upn ? me : null;
}

export function initials(me: Me): string {
  const source = me.name || me.upn.split("@")[0] || "?";
  const parts = source.split(/[\s._-]+/).filter(Boolean);
  const letters = parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : source.slice(0, 2);
  return letters.toUpperCase();
}

function daysUntil(isoDay: string, today: Date): number | null {
  const target = Date.parse(`${isoDay}T00:00:00Z`);
  if (Number.isNaN(target)) return null;
  const start = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  return Math.round((target - start) / 86_400_000);
}

export function connectionStatuses(body: unknown, today: Date = new Date()): ConnectionStatus[] {
  const items = (body as { connections?: unknown })?.connections;
  if (!Array.isArray(items)) return [];
  return items
    .filter((c): c is Record<string, unknown> => !!c && typeof c === "object" && !!str(c.id))
    .map((c) => {
      const id = str(c.id);
      const label = str(c.description) || id;
      if (c.connected !== true) return { id, label, state: "off", detail: "not connected" };
      const account = str(c.display) || str(c.account);
      const expires = str(c.expires_at);
      if (c.status && c.status !== "ok") {
        return { id, label, state: "warn", detail: "token rejected by the provider: connect again" };
      }
      if (c.expired === true) return { id, label, state: "warn", detail: "token expired: connect again" };
      const days = expires ? daysUntil(expires, today) : null;
      if (c.expiring_soon === true && days !== null) {
        const when = days <= 0 ? "today" : `in ${days} day${days === 1 ? "" : "s"}`;
        return { id, label, state: "warn", detail: `token expires ${when}` };
      }
      const parts = [account, expires && `expires ${expires}`].filter(Boolean);
      return { id, label, state: "ok", detail: parts.join(" · ") || "connected" };
    });
}

/** The worst state across connections, for the badge on the user button. */
export function overallState(statuses: ConnectionStatus[]): ConnectionState | null {
  if (statuses.some((s) => s.state === "warn")) return "warn";
  if (statuses.some((s) => s.state === "ok")) return "ok";
  return statuses.length ? "off" : null;
}
