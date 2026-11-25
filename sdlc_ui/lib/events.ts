// ADK events (from the agent runtime) to AG-UI: live events while the agent answers, and a stored session's
// events as chat history. Pure functions, no I/O: unit-tested in tests/events.test.ts.
//
// The runtime's JSON may use camelCase or snake_case field names (functionCall / function_call); both are read.

import { type BaseEvent, EventType } from "@ag-ui/client";

import { TITLE_KEY } from "./backends.ts";

type Part = {
  text?: string;
  thought?: boolean;
  functionCall?: Call;
  function_call?: Call;
  functionResponse?: Result;
  function_response?: Result;
};
type Call = { id?: string; name?: string; args?: unknown };
type Result = { id?: string; name?: string; response?: unknown };
type AdkEvent = {
  id?: string;
  author?: string;
  partial?: boolean;
  content?: { role?: string; parts?: Part[] };
  errorCode?: string;
  error_code?: string;
  error?: unknown;
};

const call = (p: Part) => p.functionCall ?? p.function_call;
const result = (p: Part) => p.functionResponse ?? p.function_response;

let counter = 0;
const nextId = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${(counter++).toString(36)}`;

function visibleText(parts: Part[]): string {
  return parts
    .filter((p) => typeof p.text === "string" && !p.thought)
    .map((p) => p.text)
    .join("");
}

/** The AG-UI events for one item of the agent's stream. */
export function adkToAgui(item: unknown): BaseEvent[] {
  if (!item || typeof item !== "object") return [];
  const event = item as AdkEvent;
  if (event.error !== undefined || event.errorCode || event.error_code) {
    return [{ type: EventType.RUN_ERROR, message: "The agent could not answer. Please try again.", code: "agent_error" } as BaseEvent];
  }
  const parts = event.content?.parts ?? [];
  if (event.partial || !parts.length || event.author === "user") return [];
  const id = event.id || nextId("evt");
  const out: BaseEvent[] = [];
  const results = parts.filter(result);
  if (results.length) {
    results.forEach((p, i) => {
      const r = result(p) ?? {};
      out.push({
        type: EventType.TOOL_CALL_RESULT,
        messageId: `${id}-r${i}`,
        toolCallId: r.id || `${id}-c${i}`,
        content: JSON.stringify(r.response ?? null),
        role: "tool",
      } as BaseEvent);
    });
    return out;
  }
  const text = visibleText(parts);
  if (text) {
    out.push({ type: EventType.TEXT_MESSAGE_START, messageId: id, role: "assistant" } as BaseEvent);
    out.push({ type: EventType.TEXT_MESSAGE_CONTENT, messageId: id, delta: text } as BaseEvent);
    out.push({ type: EventType.TEXT_MESSAGE_END, messageId: id } as BaseEvent);
  }
  parts.filter(call).forEach((p, i) => {
    const c = call(p) ?? {};
    const toolCallId = c.id || `${id}-c${i}`;
    out.push({ type: EventType.TOOL_CALL_START, toolCallId, toolCallName: c.name ?? "tool", parentMessageId: id } as BaseEvent);
    out.push({ type: EventType.TOOL_CALL_ARGS, toolCallId, delta: JSON.stringify(c.args ?? {}) } as BaseEvent);
    out.push({ type: EventType.TOOL_CALL_END, toolCallId } as BaseEvent);
  });
  return out;
}

export type Message = Record<string, unknown>;

/** A stored session's conversation as AG-UI messages (for a MESSAGES_SNAPSHOT when a chat is reopened). */
export function historyMessages(session: unknown): Message[] {
  const events = (session as { events?: unknown })?.events;
  if (!Array.isArray(events)) return [];
  const messages: Message[] = [];
  events.forEach((raw, n) => {
    const event = (raw ?? {}) as AdkEvent;
    const parts = event.content?.parts ?? [];
    const id = event.id || `h${n}`;
    if (!parts.length || event.partial) return;
    if (event.author === "user") {
      const text = visibleText(parts);
      if (text) messages.push({ id, role: "user", content: text });
      return;
    }
    const results = parts.filter(result);
    if (results.length) {
      results.forEach((p, i) => {
        const r = result(p) ?? {};
        messages.push({ id: `${id}-r${i}`, role: "tool", toolCallId: r.id || `${id}-c${i}`, content: JSON.stringify(r.response ?? null) });
      });
      return;
    }
    const calls = parts.filter(call).map((p, i) => {
      const c = call(p) ?? {};
      return { id: c.id || `${id}-c${i}`, type: "function", function: { name: c.name ?? "tool", arguments: JSON.stringify(c.args ?? {}) } };
    });
    const text = visibleText(parts);
    if (text || calls.length) {
      messages.push({ id, role: "assistant", ...(text ? { content: text } : {}), ...(calls.length ? { toolCalls: calls } : {}) });
    }
  });
  return messages;
}

export type ChatSummary = { id: string; title: string; updatedAt: string };

// ADK session IDs: UUIDs locally, digits on Agent Runtime
export const CHAT_ID = /^[A-Za-z0-9_-]{1,128}$/;

function updatedAt(value: unknown): string {
  if (typeof value === "number") return new Date(value * (value < 1e12 ? 1000 : 1)).toISOString();
  if (typeof value === "string" && !Number.isNaN(new Date(value).getTime())) return new Date(value).toISOString();
  return "";
}

/** The user's chats from `async_list_sessions`, newest first. */
export function chatSummaries(output: unknown): ChatSummary[] {
  const sessions = (output as { sessions?: unknown })?.sessions;
  if (!Array.isArray(sessions)) return [];
  return sessions
    .map((s) => {
      const session = (s ?? {}) as { id?: unknown; state?: Record<string, unknown>; lastUpdateTime?: unknown; last_update_time?: unknown };
      const title = session.state?.[TITLE_KEY];
      return {
        id: typeof session.id === "string" ? session.id : "",
        title: typeof title === "string" && title ? title : "New chat",
        updatedAt: updatedAt(session.lastUpdateTime ?? session.last_update_time),
      };
    })
    .filter((c) => CHAT_ID.test(c.id))
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

/** The text of the latest user message: each run sends only the new turn; the session holds the rest. */
export function latestUserText(messages: { role?: string; content?: unknown }[]): string {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.role !== "user") continue;
    if (typeof m.content === "string") return m.content;
    if (Array.isArray(m.content)) {
      return m.content
        .map((c) => (c && typeof c === "object" && (c as { type?: string }).type === "text" ? String((c as { text?: unknown }).text ?? "") : ""))
        .join("");
    }
  }
  return "";
}
