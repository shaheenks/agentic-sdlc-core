"use client";

// The chat's message list with how long each answer took (lib/timing.ts): under each assistant message, its time
// after the user's message, and under the turn's last one the turn's total.

import { CopilotChatAssistantMessage, CopilotChatMessageView } from "@copilotkit/react-core/v2";
import { type ComponentProps, createContext, useContext } from "react";

import { RunClock } from "@/lib/timing";

type ViewProps = ComponentProps<typeof CopilotChatMessageView>;
type AssistantProps = ComponentProps<typeof CopilotChatAssistantMessage>;
type Timings = { clock: RunClock; last: Set<string> };

const TimingContext = createContext<Timings | null>(null);
const clocks = new Map<string, RunClock>();

/** One clock per chat for as long as the page is open. */
export function clockFor(chatId: string): RunClock {
  let clock = clocks.get(chatId);
  if (!clock) {
    clock = new RunClock();
    clocks.set(chatId, clock);
  }
  return clock;
}

function TimedAssistant(props: AssistantProps) {
  const timings = useContext(TimingContext);
  const id = props.message?.id ?? "";
  const label = timings && id ? timings.clock.label(id, timings.last.has(id)) : "";
  return (
    <div className="timed">
      <CopilotChatAssistantMessage {...props} />
      {label && (
        <small className="elapsed" title="Time after your message">
          {label}
        </small>
      )}
    </div>
  );
}

export function timedMessageView(clock: RunClock): typeof CopilotChatMessageView {
  function TimedMessageView(props: ViewProps) {
    const messages = (props.messages ?? []) as { id: string; role?: string }[];
    clock.observe(
      messages.map((m) => m.id),
      !!props.isRunning,
      Date.now(),
    );
    // the last assistant message before each user message, and the last one overall
    const last = new Set<string>();
    messages.forEach((m, i) => {
      const next = messages[i + 1];
      if (m.role === "assistant" && (!next || next.role === "user")) last.add(m.id);
    });
    return (
      <TimingContext.Provider value={{ clock, last }}>
        <CopilotChatMessageView {...props} assistantMessage={TimedAssistant as never} />
      </TimingContext.Provider>
    );
  }
  // the slot expects the view's static members (Cursor and the like) too
  return Object.assign(TimedMessageView, CopilotChatMessageView) as unknown as typeof CopilotChatMessageView;
}
