"use client";

// Opens the document viewer (ArtifactViewer) when the panel or a chat card asks for it
// (OPEN_ARTIFACT), and posts "Attach to chat" into the open conversation exactly like the chat
// input does: a user message on the chat's agent, then a run. Must render inside <CopilotKit>.

import { useAgent, useCopilotKit } from "@copilotkit/react-core/v2";
import { useCallback, useEffect, useState } from "react";

import { ArtifactViewer, OPEN_ARTIFACT } from "@/components/ArtifactViewer";

type Target = { id: string; name: string };

export function ArtifactReviewHost() {
  const [target, setTarget] = useState<Target | null>(null);
  const { agent } = useAgent();
  const { copilotkit } = useCopilotKit();

  useEffect(() => {
    const onOpen = (e: Event) => {
      const detail = (e as CustomEvent<Target>).detail;
      if (detail && typeof detail.id === "string") setTarget({ id: detail.id, name: String(detail.name ?? "") });
    };
    window.addEventListener(OPEN_ARTIFACT, onOpen);
    return () => window.removeEventListener(OPEN_ARTIFACT, onOpen);
  }, []);

  const attach = useCallback(
    async (message: string): Promise<string | null> => {
      if (agent.isRunning) return "The assistant is still answering. Try again when it has finished.";
      agent.addMessage({ id: crypto.randomUUID(), role: "user", content: message });
      void copilotkit.runAgent({ agent }).catch((error: unknown) => {
        console.error("attach: run failed", error);
      });
      return null;
    },
    [agent, copilotkit],
  );

  if (!target) return null;
  return <ArtifactViewer artifact={target} onClose={() => setTarget(null)} onAttach={attach} />;
}
