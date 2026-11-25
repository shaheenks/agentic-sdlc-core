"use client";

import "@copilotkit/react-core/v2/styles.css";

import { CopilotChat, CopilotKit } from "@copilotkit/react-core/v2";
import { useCallback, useEffect, useState } from "react";

import { ChatList } from "@/components/ChatList";
import { api, type Chat, latestTurn } from "@/lib/client";

// A chat is a runtime session of the signed-in user (FR-AGT-005, FR-WFL-009). The open chat is in the URL
// (?chat=<id>), so a reload, a bookmark or signing in again reopens it; its history is replayed from the
// runtime by the server, for this user only.
const CHAT_ID = /^[A-Za-z0-9_-]{1,128}$/;

export default function ChatPage() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [chatId, setChatId] = useState<string | null>(null);
  const [error, setError] = useState("");

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

  const startNew = useCallback(async () => {
    try {
      const { id } = await api<{ id: string }>("/api/chats", { method: "POST" });
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
    refresh();
    const id = new URLSearchParams(window.location.search).get("chat");
    if (id && CHAT_ID.test(id)) setChatId(id);
    // a new chat gets its title from its first message: pick it up while the page is open
    const timer = setInterval(refresh, 15_000);
    return () => clearInterval(timer);
  }, [refresh]);

  return (
    <CopilotKit runtimeUrl="/api/copilotkit" useSingleEndpoint={false} showDevConsole={false} enableInspector={false} messageFilter={latestTurn}>
      <div className="workspace">
        <ChatList chats={chats} activeId={chatId} onSelect={open} onNew={startNew} onDelete={remove} />
        <section className="chat">
          {error && <p className="error">{error}</p>}
          {chatId ? (
            <CopilotChat
              key={chatId}
              threadId={chatId}
              onError={() => refresh()}
              labels={{ chatInputPlaceholder: "Ask about requirements, designs, decisions or code…" }}
            />
          ) : (
            <div className="welcome">
              <h1>Ask the knowledge you may read</h1>
              <p>Answers cite their sources. Start a new chat, or reopen one of yours.</p>
              <button type="button" className="primary" onClick={startNew}>
                New chat
              </button>
            </div>
          )}
        </section>
      </div>
    </CopilotKit>
  );
}
