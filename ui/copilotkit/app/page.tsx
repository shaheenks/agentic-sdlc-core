"use client";

import "@copilotkit/react-core/v2/styles.css";

import { CopilotChat, CopilotKit } from "@copilotkit/react-core/v2";

import { toolRenderers } from "@/components/renderers";

// The runtime is same-origin (behind the same oauth2-proxy), so the browser sends only its
// proxy session cookie; the proxy adds the user's token server side.
export default function ChatPage() {
  return (
    <CopilotKit
      runtimeUrl="/chat/api/copilotkit"
      useSingleEndpoint={false}
      renderToolCalls={toolRenderers}
      showDevConsole={false}
      enableInspector={false}
    >
      <main className="shell">
        <header className="topbar">
          <span className="brand">SDLC assistant</span>
          <nav>
            <a href="/chat/connections">Connections</a>
            <a href="/dev-ui/">Developer UI</a>
            <a href="/oauth2/sign_out">Sign out</a>
          </nav>
        </header>
        <div className="chat">
          <CopilotChat
            labels={{
              chatInputPlaceholder: "Ask about your team's code, runbooks, incidents…",
            }}
          />
        </div>
      </main>
    </CopilotKit>
  );
}
