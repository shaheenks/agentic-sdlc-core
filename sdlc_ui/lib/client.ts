// Browser-side calls to this origin's BFF. No secrets here: the server verifies the user on every request.

export type Chat = { id: string; title: string; updatedAt: string; team?: string };

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    cache: "no-store",
    headers: { "x-sdlc-request": "1", ...(init.body ? { "content-type": "application/json" } : {}), ...init.headers },
  });
  if (response.status === 204) return undefined as T;
  const body = (await response.json().catch(() => ({}))) as { message?: string };
  if (!response.ok) throw new ApiError(response.status, body.message ?? `HTTP ${response.status}`);
  return body as T;
}

/** "14:05" today, "3 Nov" this year, "3 Nov 2025" before. */
export function formatWhen(iso: string, now: Date = new Date()): string {
  const when = new Date(iso);
  if (!iso || Number.isNaN(when.getTime())) return "";
  if (when.toDateString() === now.toDateString()) {
    return when.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }
  const sameYear = when.getFullYear() === now.getFullYear();
  return when.toLocaleDateString(undefined, { day: "numeric", month: "short", ...(sameYear ? {} : { year: "numeric" }) });
}

/** The messages a run sends: from the last user message on (the runtime session holds the rest). */
export function latestTurn<T extends { role?: string }>(messages: T[]): T[] {
  for (let i = messages.length - 1; i >= 0; i--) if (messages[i].role === "user") return messages.slice(i);
  return messages;
}
