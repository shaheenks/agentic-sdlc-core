"use client";

// Conversation history sidebar (version-02 N15): "New chat" and the caller's previous threads
// from GET /threads (agent, same origin through oauth2-proxy; per user by the token oid).
// Refreshes on load, on window focus and whenever a run finishes (a new thread appears after
// its first answer). Opening a thread is the page's job (CopilotChat threadId).

import { useAgent } from "@copilotkit/react-core/v2";
import { useCallback, useEffect, useState } from "react";

import { formatUpdated, parseThreads, type ThreadSummary } from "@/lib/threads";

type Props = {
  activeId: string | null;
  onSelect: (threadId: string) => void;
  onNew: () => void;
};

export function ThreadList({ activeId, onSelect, onNew }: Props) {
  const [threads, setThreads] = useState<ThreadSummary[] | null>(null);
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
      {threads !== null && threads.length === 0 && <p className="threads-empty">No previous chats yet.</p>}
      <ul className="thread-list">
        {(threads ?? []).map((t) => (
          <li key={t.id}>
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
          </li>
        ))}
      </ul>
    </aside>
  );
}
