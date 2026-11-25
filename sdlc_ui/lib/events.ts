// ADK events (from the agent runtime) to AG-UI: live events while the agent answers, and a stored session's
// events as chat history. Pure functions, no I/O: unit-tested in tests/events.test.ts.
//
// The runtime's JSON may use camelCase or snake_case field names (functionCall / function_call); both are read.
//
// Workflows (FR-SDLC-002 to FR-SDLC-005) run inside the root agent's tool calls. Their drafting and reviewing
// sub-agents write text the user should not see as chat (drafts, reviewers' JSON); only the root agent's messages
// are shown, plus each workflow question (`adk_request_input`), which the browser answers (FR-HUM-001).

import { type BaseEvent, EventType } from "@ag-ui/client";

import { TEAM_KEY, TITLE_KEY } from "./backends.ts";

export const ROOT_AGENT = "user_agent";
export const REQUEST_INPUT = "adk_request_input";
// ADK function call IDs (adk-<uuid>) and interrupt IDs (UUIDs, or names the workflow chose)
export const CALL_ID = /^[A-Za-z0-9_:.-]{1,200}$/;

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
const fromRoot = (event: AdkEvent) => !event.author || event.author === ROOT_AGENT;
const isQuestion = (p: Part) => call(p)?.name === REQUEST_INPUT;

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
  const all = event.content?.parts ?? [];
  if (event.partial || !all.length || event.author === "user") return [];
  // a workflow's own agents and steps: only its questions reach the chat
  const parts = fromRoot(event) ? all : all.filter(isQuestion);
  if (!parts.length) return [];
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
    const all = event.content?.parts ?? [];
    const id = event.id || `h${n}`;
    if (!all.length || event.partial) return;
    if (event.author === "user") {
      const text = visibleText(all);
      if (text) messages.push({ id, role: "user", content: text });
      // the user's answers to workflow questions
      all.filter(result).forEach((p, i) => {
        const r = result(p) ?? {};
        if (r.name === REQUEST_INPUT && r.id) {
          messages.push({ id: `${id}-a${i}`, role: "tool", toolCallId: r.id, content: JSON.stringify(r.response ?? null) });
        }
      });
      return;
    }
    const parts = fromRoot(event) ? all : all.filter(isQuestion);
    if (!parts.length) return;
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

export type ChatSummary = { id: string; title: string; updatedAt: string; team?: string };

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
      const team = session.state?.[TEAM_KEY];
      return {
        id: typeof session.id === "string" ? session.id : "",
        title: typeof title === "string" && title ? title : "New chat",
        updatedAt: updatedAt(session.lastUpdateTime ?? session.last_update_time),
        ...(typeof team === "string" && team ? { team } : {}),
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

export type AdkContent = { role: "user"; parts: { function_response: { id: string; name: string; response: unknown } }[] };
type TurnMessage = { role?: string; content?: unknown; toolCallId?: unknown; toolCalls?: unknown };

function parseAnswer(content: unknown): unknown {
  if (typeof content !== "string") return content ?? "";
  try {
    return JSON.parse(content);
  } catch {
    return content;
  }
}

/** What a run sends the runtime: the user's answer to a workflow question when the turn ends with one (as the
 *  function response that resumes the workflow), otherwise the latest user text. Only an answer to a question
 *  this conversation asked is sent as such; anything else is ignored. */
export function turnInput(messages: TurnMessage[]): string | AdkContent {
  const last = messages[messages.length - 1];
  const id = last?.toolCallId;
  if (last?.role === "tool" && typeof id === "string" && CALL_ID.test(id)) {
    const asked = messages.some(
      (m) =>
        m.role === "assistant" &&
        Array.isArray(m.toolCalls) &&
        m.toolCalls.some((c) => c && typeof c === "object" && (c as Call & { function?: { name?: string } }).id === id && (c as { function?: { name?: string } }).function?.name === REQUEST_INPUT),
    );
    if (asked) {
      return { role: "user", parts: [{ function_response: { id, name: REQUEST_INPUT, response: { result: parseAnswer(last.content) } } }] };
    }
  }
  return latestUserText(messages);
}

/** Why a run failed, in words for the user: never the error's details, which could carry data. */
export function failureText(item: unknown): string {
  const raw = JSON.stringify(item ?? "");
  if (/\b(503|429|UNAVAILABLE|RESOURCE_EXHAUSTED)\b/.test(raw)) {
    return "The model service was busy and the run stopped. Please try again in a moment.";
  }
  return "The run stopped with an error. Please try again.";
}

/** A failed run, shown instead of a silent error: its open tool calls close as failed, and a message says why. */
export function failureEvents(openToolCalls: string[], item: unknown): BaseEvent[] {
  const text = failureText(item);
  const id = nextId("failed");
  return [
    ...openToolCalls.map(
      (toolCallId, i) =>
        ({
          type: EventType.TOOL_CALL_RESULT,
          messageId: `${id}-r${i}`,
          toolCallId,
          content: JSON.stringify({ error: "failed", message: text }),
          role: "tool",
        }) as BaseEvent,
    ),
    { type: EventType.TEXT_MESSAGE_START, messageId: id, role: "assistant" } as BaseEvent,
    { type: EventType.TEXT_MESSAGE_CONTENT, messageId: id, delta: text } as BaseEvent,
    { type: EventType.TEXT_MESSAGE_END, messageId: id } as BaseEvent,
  ];
}

const REVIEWER = /^review_(structure|style|clarity|design|readiness|technical_detail|simplicity)$/;
const REVIEWERS = 7;
const TOOL_WORDS: Record<string, string> = {
  knowledge_search: "searching knowledge",
  knowledge_graph: "exploring related knowledge",
  repo_read_file: "reading code",
  repo_list: "browsing the repository",
  jira_get_issue: "reading Jira",
  jira_search: "searching Jira",
  team_systems: "reading the team's systems",
};

/** A running workflow's stage, from its own agents' events (which the chat does not show): drafting, how many of
 *  the seven reviewers are done, revising, waiting for the user. Sent to the browser as the agent's state. */
export class WorkflowProgress {
  private readonly reviewed = new Set<string>();
  private last = "";

  update(item: unknown): string | null {
    const event = (item ?? {}) as AdkEvent;
    const author = event.author ?? "";
    const parts = event.content?.parts ?? [];
    if (event.partial || !parts.length || !author || author === ROOT_AGENT || author === "user") return null;
    const toolName = parts.map((p) => call(p)?.name).find((n) => n && n !== REQUEST_INPUT);
    const doing = toolName ? TOOL_WORDS[toolName] ?? toolName.replace(/_/g, " ") : "";
    let label = "";
    if (parts.some(isQuestion)) label = "Waiting for your answer";
    else if (author.endsWith("_reviser")) {
      this.reviewed.clear();
      label = doing ? `Revising (${doing})` : "Revising with the chosen findings";
    } else if (author.endsWith("_drafter")) label = doing ? `Drafting (${doing})` : "Drafting";
    else if (REVIEWER.test(author)) {
      if (visibleText(parts)) {
        if (this.reviewed.size === REVIEWERS) this.reviewed.clear(); // the next round
        this.reviewed.add(author);
      }
      label = `Reviewing: ${this.reviewed.size} of ${REVIEWERS} reviewers done`;
    } else return null;
    if (label === this.last) return null;
    this.last = label;
    return label;
  }
}
