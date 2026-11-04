// Conversation history for the chat app (version-02 N15). No React, no I/O: unit-tested in
// tests/threads.test.ts.
//
// - GET /threads (agent, same origin through oauth2-proxy): the caller's own conversations,
//   {threadId, title, updatedAt}, newest first.
// - Opening one: CopilotChat connects to the thread, and PassThroughAgentRunner.connect (server
//   side) reads that thread's messages from the agent's /agents/state as the same user and replays
//   them as one MESSAGES_SNAPSHOT (historyMessages cleans that response).
// - Runs send only the latest turn (latestTurn): the agent already holds the conversation.

export type ThreadSummary = { id: string; title: string; updatedAt: string };

// AG-UI thread ids (CopilotKit UUIDs) and ADK session ids (UUIDs, or digits on Agent Engine)
export const THREAD_ID = /^[A-Za-z0-9_-]{1,128}$/;

const str = (value: unknown): string => (typeof value === "string" ? value : "");

export function parseThreads(body: unknown): ThreadSummary[] {
  const items = (body as { threads?: unknown })?.threads;
  if (!Array.isArray(items)) return [];
  return items
    .filter((t): t is Record<string, unknown> => !!t && typeof t === "object")
    .map((t) => ({ id: str(t.threadId), title: str(t.title), updatedAt: str(t.updatedAt) }))
    .filter((t) => THREAD_ID.test(t.id) && t.title);
}

/** The thread named in the page URL (`?thread=<id>`), if it is a valid id. */
export function threadFromSearch(search: string): string | null {
  const id = new URLSearchParams(search).get("thread");
  return id && THREAD_ID.test(id) ? id : null;
}

export function newThreadId(): string {
  return crypto.randomUUID();
}

/** "14:05" today, "3 Nov" this year, "3 Nov 2025" before. */
export function formatUpdated(iso: string, now: Date = new Date()): string {
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return "";
  if (when.toDateString() === now.toDateString()) {
    return when.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }
  const sameYear = when.getFullYear() === now.getFullYear();
  return when.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    ...(sameYear ? {} : { year: "numeric" }),
  });
}

/**
 * The messages a run sends to the agent: from the last user message on. The agent stores the
 * conversation itself, so earlier turns (including history replayed with ids the agent did not
 * issue) are never sent back as new input.
 */
export function latestTurn<T extends { role?: string }>(messages: T[]): T[] {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "user") return messages.slice(i);
  }
  return messages;
}

const HISTORY_ROLES = new Set(["user", "assistant", "tool"]);

/**
 * The messages of an /agents/state response, ready for a MESSAGES_SNAPSHOT: user, assistant and
 * tool messages only, null fields dropped (the AG-UI schema has optional, not nullable, fields).
 */
export function historyMessages(body: unknown): Record<string, unknown>[] {
  const state = body as { threadExists?: unknown; messages?: unknown };
  if (state?.threadExists !== true || !Array.isArray(state.messages)) return [];
  return state.messages
    .filter(
      (m): m is Record<string, unknown> =>
        !!m && typeof m === "object" && HISTORY_ROLES.has(str((m as { role?: unknown }).role)) && !!str((m as { id?: unknown }).id),
    )
    .map((m) => Object.fromEntries(Object.entries(m).filter(([, v]) => v !== null && v !== undefined)));
}
