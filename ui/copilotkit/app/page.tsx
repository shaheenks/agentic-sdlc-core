"use client";

import "@copilotkit/react-core/v2/styles.css";

import { CopilotChat, CopilotKit } from "@copilotkit/react-core/v2";
import { useCallback, useEffect, useState } from "react";

import { toolRenderers } from "@/components/renderers";
import { ThreadList } from "@/components/ThreadList";
import { UserStatus } from "@/components/UserStatus";
import { latestTurn, newThreadId, threadFromSearch } from "@/lib/threads";

// The runtime is same-origin (behind the same oauth2-proxy), so the browser sends only its
// proxy session cookie; the proxy adds the user's token server side.
//
// History (version-02 N15): the open thread is in the URL (?thread=<id>), so a reload or a
// bookmark reopens it; CopilotChat connects to it and the runtime replays its messages from the
// agent. Runs send only the latest turn (latestTurn): the agent keeps the conversation.
export default function ChatPage() {
  const [threadId, setThreadId] = useState<string | null>(null);

  const open = useCallback((id: string) => {
    setThreadId(id);
    window.history.replaceState(null, "", `?thread=${encodeURIComponent(id)}`);
  }, []);

  useEffect(() => {
    open(threadFromSearch(window.location.search) ?? newThreadId());
  }, [open]);

  return (
    <CopilotKit
      runtimeUrl="/chat/api/copilotkit"
      useSingleEndpoint={false}
      renderToolCalls={toolRenderers}
      showDevConsole={false}
      enableInspector={false}
      messageFilter={latestTurn}
    >
      <main className="shell">
        <header className="topbar">
          <span className="brand">SDLC assistant</span>
          <nav>
            <a href="/chat/connections">Connections</a>
            <a href="/dev-ui/">Developer UI</a>
            <UserStatus />
          </nav>
        </header>
        <div className="workspace">
          <ThreadList activeId={threadId} onSelect={open} onNew={() => open(newThreadId())} />
          <div className="chat">
            {threadId && (
              <CopilotChat
                threadId={threadId}
                labels={{
                  chatInputPlaceholder: "Ask about your team's code, runbooks, incidents…",
                }}
              />
            )}
          </div>
        </div>
      </main>
    </CopilotKit>
  );
}
