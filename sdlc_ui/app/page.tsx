"use client";

import "@copilotkit/react-core/v2/styles.css";

import { CopilotChat, CopilotKit, useConfigureSuggestions } from "@copilotkit/react-core/v2";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ChatList } from "@/components/ChatList";
import { clockFor, timedMessageView } from "@/components/TimedMessages";
import { ToolCards } from "@/components/ToolCards";
import { WorkflowQuestions } from "@/components/WorkflowQuestions";
import { api, type Chat, latestTurn } from "@/lib/client";

// A chat is a runtime session of the signed-in user (FR-AGT-005, FR-WFL-009). The open chat is in the URL
// (?chat=<id>), so a reload, a bookmark or signing in again reopens it; its history is replayed from the
// runtime by the server, for this user only.
const CHAT_ID = /^[A-Za-z0-9_-]{1,128}$/;

// In a team chat, the workflows start from these (FR-SDLC-002, FR-SDLC-003); the agent asks for what it needs.
function TeamSuggestions({ team }: { team?: string }) {
  useConfigureSuggestions(
    team
      ? {
          available: "before-first-message",
          suggestions: [
            { title: "Draft features and stories", message: `Let's draft a feature and its user stories for ${team}.` },
            { title: "Draft a design", message: `Let's draft a design specification for ${team}.` },
            { title: "Design from a Jira feature", message: `Draft a design from a Jira feature of ${team}.` },
          ],
        }
      : null,
    [team],
  );
  return null;
}

export default function ChatPage() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [teams, setTeams] = useState<string[]>([]);
  const [chatId, setChatId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const messageView = useMemo(() => (chatId ? timedMessageView(clockFor(chatId)) : undefined), [chatId]);

  const refresh = useCallback(() => {
    api<{ chats: Chat[] }>("/api/chats").then(
      (r) => setChats(r.chats),
      (e: Error) => setError(e.message),
    );
  }, []);

  const open = useCallback((id: string) => {
    setChatId(id);
    window.history.replaceState(null, "", `/?chat=${encodeURIComponent(id)}`);
  }, []);

  const startNew = useCallback(async (team?: string) => {
    try {
      const body = team ? JSON.stringify({ team }) : undefined;
      const { id } = await api<{ id: string }>("/api/chats", { method: "POST", ...(body ? { body } : {}) });
      open(id);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }, [open, refresh]);

  const remove = useCallback(
    async (id: string) => {
      await api(`/api/chats/${encodeURIComponent(id)}`, { method: "DELETE" }).catch(() => undefined);
      setChats((cs) => cs.filter((c) => c.id !== id));
      if (id === chatId) setChatId(null);
    },
    [chatId],
  );

  useEffect(() => {
    api<{ teams?: Record<string, unknown> }>("/api/me").then(
      (me) => setTeams(Object.keys(me.teams ?? {})),
      () => setTeams([]),
    );
  }, []);

  useEffect(() => {
    refresh();
    const id = new URLSearchParams(window.location.search).get("chat");
    if (id && CHAT_ID.test(id)) setChatId(id);
    // a new chat gets its title from its first message: pick it up while the page is open
    const timer = setInterval(refresh, 15_000);
    return () => clearInterval(timer);
  }, [refresh]);

  return (
    <CopilotKit runtimeUrl="/api/copilotkit" useSingleEndpoint={false} showDevConsole={false} enableInspector={false} messageFilter={latestTurn}>
      <WorkflowQuestions />
      <ToolCards />
      <TeamSuggestions team={chats.find((c) => c.id === chatId)?.team} />
      <div className="workspace">
        <ChatList chats={chats} teams={teams} activeId={chatId} onSelect={open} onNew={startNew} onDelete={remove} />
        <section className="chat">
          {error && <p className="error">{error}</p>}
          {chatId ? (
            <CopilotChat
              key={chatId}
              threadId={chatId}
              messageView={messageView}
              onError={() => refresh()}
              labels={{ chatInputPlaceholder: "Ask about requirements, designs, decisions or code…" }}
            />
          ) : (
            <div className="welcome">
              <h1>Ask the knowledge you may read</h1>
              <p>Answers cite their sources. Start a new chat, or reopen one of yours.</p>
              <button type="button" className="primary" onClick={() => startNew()}>
                New chat
              </button>
            </div>
          )}
        </section>
      </div>
    </CopilotKit>
  );
}
