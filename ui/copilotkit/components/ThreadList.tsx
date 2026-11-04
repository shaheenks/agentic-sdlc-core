"use client";

// Conversation history sidebar (version-02 N15): "New chat" and the caller's previous threads
// from GET /threads (agent, same origin through oauth2-proxy; per user by the token oid).
// Refreshes on load, on window focus and whenever a run finishes (a new thread appears after
// its first answer). Opening a thread is the page's job (CopilotChat threadId).
// Delete: a trash button per row asks inline, then DELETE /threads/<id> (the agent deletes the
// caller's own conversation only). The row goes at once and comes back if the agent refuses.

import { useAgent } from "@copilotkit/react-core/v2";
import { useCallback, useEffect, useState } from "react";

import {
  deleteThreadRequest,
  formatUpdated,
  parseThreads,
  type ThreadSummary,
  withoutThread,
} from "@/lib/threads";

type Props = {
  activeId: string | null;
  onSelect: (threadId: string) => void;
  onNew: () => void;
  onDeleted: (threadId: string) => void;
};

export function ThreadList({ activeId, onSelect, onNew, onDeleted }: Props) {
  const [threads, setThreads] = useState<ThreadSummary[] | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { agent } = useAgent();
  const running = agent.isRunning;

  const load = useCallback(async () => {
    try {
      const response = await fetch("/threads", {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (response.ok) setThreads(parseThreads(await response.json()));
    } catch {
      // keep the last list; the chat itself still works
    }
  }, []);

  const remove = useCallback(
    async (thread: ThreadSummary) => {
      const request = deleteThreadRequest(thread.id);
      setConfirming(null);
      if (!request) return;
      setError(null);
      setThreads((list) => (list ? withoutThread(list, thread.id) : list));
      try {
        const response = await fetch(request.url, request.init);
        if (!response.ok && response.status !== 404) throw new Error(String(response.status));
        onDeleted(thread.id);
      } catch {
        setError("Could not delete the chat. Please try again.");
      }
      void load(); // the agent's list is the truth either way
    },
    [load, onDeleted],
  );

  useEffect(() => {
    if (!running) void load();
  }, [running, load]);

  useEffect(() => {
    const refresh = () => document.visibilityState === "visible" && void load();
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [load]);

  return (
    <aside className="threads" aria-label="Previous chats">
      <button type="button" className="new-chat" onClick={onNew}>
        + New chat
      </button>
      {error && (
        <p className="threads-error" role="alert">
          {error}
        </p>
      )}
      {threads !== null && threads.length === 0 && <p className="threads-empty">No previous chats yet.</p>}
      <ul className="thread-list">
        {(threads ?? []).map((t) =>
          confirming === t.id ? (
            <li key={t.id} className="thread-confirm">
              <span>Delete this chat?</span>
              <span className="thread-confirm-actions">
                <button type="button" className="danger" onClick={() => void remove(t)} autoFocus>
                  Delete
                </button>
                <button type="button" onClick={() => setConfirming(null)}>
                  Cancel
                </button>
              </span>
            </li>
          ) : (
            <li key={t.id} className="thread-row">
              <button
                type="button"
                className={t.id === activeId ? "thread active" : "thread"}
                aria-current={t.id === activeId ? "true" : undefined}
                onClick={() => onSelect(t.id)}
                title={t.title}
              >
                <span className="thread-title">{t.title}</span>
                <span className="thread-when">{formatUpdated(t.updatedAt)}</span>
              </button>
              <button
                type="button"
                className="thread-delete"
                aria-label={`Delete chat: ${t.title}`}
                title="Delete chat"
                onClick={() => setConfirming(t.id)}
              >
                <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
                  <path
                    d="M6 2h4m-7 2h10m-1 0-.6 9a1 1 0 0 1-1 .9H5.6a1 1 0 0 1-1-.9L4 4m2.5 2.5v5m3-5v5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.3"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </li>
          ),
        )}
      </ul>
    </aside>
  );
}
