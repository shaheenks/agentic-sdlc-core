// The `agent-runtime` backend (CH-0016): the user agent on Agent Runtime, spoken to as AG-UI.
// No React: unit-tested in tests/agent-runtime.test.ts.
//
// - Calls the engine's methods (`stream_query`, `list_threads`, `get_thread`, `delete_thread`) as
//   the UI service account; the USER is the Google ID token passed as `user_token`, which the
//   engine re-validates. The token comes from `agent.headers` (set per request by the CopilotKit
//   runtime from the header the route handler wrote after its checks) and is never logged.
// - The CopilotKit thread id is passed as `thread_id`: the engine keeps one session per user and
//   thread, so this process stores nothing.
// - ADK events are mapped to AG-UI events the way ag_ui_adk does for /agui: text messages, tool
//   calls, and tool results as JSON text (the card renderers read them unchanged).
// - Refusals (`{"refusal": {code, message}}`, CH-0019/CH-0025) end the run with RUN_ERROR.

import { AbstractAgent, type BaseEvent, EventType, type RunAgentInput } from "@ag-ui/client";
import { Observable } from "rxjs";

import type { ServiceTokens } from "./gcp.ts";
import { TOKEN_HEADER } from "./runner.ts";

export type EngineSettings = { engine: string; region: string };

export function engineSettings(env: Record<string, string | undefined> = process.env): EngineSettings {
  const engine = env.SDLC_AGENT_ENGINE ?? "";
  const match = /^projects\/[^/]+\/locations\/([a-z0-9-]+)\/reasoningEngines\/\d+$/.exec(engine);
  if (!match) throw new Error("SDLC_AGENT_ENGINE must be projects/<p>/locations/<region>/reasoningEngines/<id>");
  return { engine, region: match[1] };
}

export type Refusal = { code: string; message: string };

export function refusalOf(value: unknown): Refusal | null {
  const r = (value as { refusal?: unknown } | null)?.refusal as Record<string, unknown> | undefined;
  if (!r || typeof r !== "object") return null;
  return { code: String(r.code ?? "internal"), message: String(r.message ?? "the agent refused the request") };
}

export class EngineClient {
  private readonly settings: EngineSettings;
  private readonly tokens: Pick<ServiceTokens, "accessToken">;
  private readonly fetchImpl: typeof fetch;
  private readonly apiBase: string;

  constructor(
    settings: EngineSettings,
    tokens: Pick<ServiceTokens, "accessToken">,
    fetchImpl: typeof fetch = fetch,
    apiBase: string = `https://${settings.region}-aiplatform.googleapis.com/v1`,
  ) {
    this.settings = settings;
    this.tokens = tokens;
    this.fetchImpl = fetchImpl;
    this.apiBase = apiBase;
  }

  private async post(suffix: string, method: string, input: Record<string, unknown>, signal?: AbortSignal) {
    const response = await this.fetchImpl(`${this.apiBase}/${this.settings.engine}${suffix}`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${await this.tokens.accessToken()}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({ class_method: method, input }),
      cache: "no-store",
      signal,
    });
    // never the body: an Agent Runtime error can quote the request (the user's token)
    if (!response.ok) throw new Error(`Agent Runtime ${method} HTTP ${response.status}`);
    return response;
  }

  /** A non-streaming method's output (or its refusal). */
  async query(method: string, input: Record<string, unknown>): Promise<unknown> {
    const body = (await (await this.post(":query", method, input)).json()) as { output?: unknown };
    return body.output;
  }

  /** A streaming method's items, one JSON value per line (SSE `data:` framing tolerated). */
  async *stream(method: string, input: Record<string, unknown>, signal?: AbortSignal): AsyncGenerator<unknown> {
    const response = await this.post(":streamQuery?alt=sse", method, input, signal);
    if (!response.body) return;
    const decoder = new TextDecoder();
    let buffer = "";
    for await (const chunk of response.body as unknown as AsyncIterable<Uint8Array>) {
      buffer += decoder.decode(chunk, { stream: true });
      let newline = buffer.indexOf("\n");
      while (newline >= 0) {
        const item = parseLine(buffer.slice(0, newline));
        buffer = buffer.slice(newline + 1);
        if (item !== undefined) yield item;
        newline = buffer.indexOf("\n");
      }
    }
    const last = parseLine(buffer + decoder.decode());
    if (last !== undefined) yield last;
  }
}

function parseLine(line: string): unknown {
  const text = line.trim().replace(/^data:\s*/, "");
  if (!text) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    console.error("Agent Runtime: an unreadable stream line was skipped");
    return undefined;
  }
}

// --- ADK events -> AG-UI events ----------------------------------------------------------------

type Part = {
  text?: string;
  thought?: boolean;
  functionCall?: { id?: string; name?: string; args?: unknown };
  functionResponse?: { id?: string; name?: string; response?: unknown };
};
type AdkEvent = {
  id?: string;
  author?: string;
  partial?: boolean;
  content?: { parts?: Part[] };
  errorCode?: string;
};

let fallbackIds = 0;
const nextId = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${(fallbackIds++).toString(36)}`;

/** The AG-UI events for one item of the engine's stream (pure; ids from the ADK event). */
export function adkToAgui(item: unknown): BaseEvent[] {
  if (!item || typeof item !== "object") return [];
  const refused = refusalOf(item);
  if (refused) {
    return [{ type: EventType.RUN_ERROR, message: refused.message, code: refused.code } as BaseEvent];
  }
  if ("session" in item && Object.keys(item).length === 1) return []; // the engine's session id
  const event = item as AdkEvent;
  if (event.partial || !event.content?.parts?.length) {
    if (event.errorCode) {
      return [{ type: EventType.RUN_ERROR, message: "The model could not answer. Please try again.", code: "model_error" } as BaseEvent];
    }
    return [];
  }
  const id = event.id || nextId("evt");
  const parts = event.content.parts;
  const out: BaseEvent[] = [];
  const results = parts.filter((p) => p.functionResponse);
  if (results.length) {
    results.forEach((p, i) => {
      const r = p.functionResponse ?? {};
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
  if (event.author === "user") return [];
  const text = parts
    .filter((p) => p.text && !p.thought)
    .map((p) => p.text)
    .join("");
  if (text) {
    out.push({ type: EventType.TEXT_MESSAGE_START, messageId: id, role: "assistant" } as BaseEvent);
    out.push({ type: EventType.TEXT_MESSAGE_CONTENT, messageId: id, delta: text } as BaseEvent);
    out.push({ type: EventType.TEXT_MESSAGE_END, messageId: id } as BaseEvent);
  }
  parts
    .filter((p) => p.functionCall)
    .forEach((p, i) => {
      const call = p.functionCall ?? {};
      const toolCallId = call.id || `${id}-c${i}`;
      out.push({
        type: EventType.TOOL_CALL_START,
        toolCallId,
        toolCallName: call.name ?? "tool",
        parentMessageId: id,
      } as BaseEvent);
      out.push({ type: EventType.TOOL_CALL_ARGS, toolCallId, delta: JSON.stringify(call.args ?? {}) } as BaseEvent);
      out.push({ type: EventType.TOOL_CALL_END, toolCallId } as BaseEvent);
    });
  return out;
}

/** The text of the latest user message (runs send only the latest turn, lib/threads.ts). */
export function latestUserText(input: RunAgentInput): string {
  for (let i = input.messages.length - 1; i >= 0; i--) {
    const m = input.messages[i] as { role?: string; content?: unknown };
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

function headerValue(headers: Record<string, string>, name: string): string {
  for (const [key, value] of Object.entries(headers)) if (key.toLowerCase() === name) return value;
  return "";
}

/** An AG-UI agent backed by Agent Runtime's `stream_query`. */
export class AgentRuntimeAgent extends AbstractAgent {
  headers: Record<string, string> = {};
  private controller?: AbortController;
  private readonly client: EngineClient;

  constructor(client: EngineClient) {
    super();
    this.client = client;
  }

  run(input: RunAgentInput): Observable<BaseEvent> {
    const ids = { threadId: input.threadId, runId: input.runId };
    const token = headerValue(this.headers, TOKEN_HEADER);
    return new Observable<BaseEvent>((subscriber) => {
      const controller = new AbortController();
      this.controller = controller;
      subscriber.next({ type: EventType.RUN_STARTED, ...ids } as BaseEvent);
      (async () => {
        if (!token) {
          subscriber.next({ type: EventType.RUN_ERROR, message: "Sign-in required.", code: "unauthenticated" } as BaseEvent);
          return subscriber.complete();
        }
        const stream = this.client.stream(
          "stream_query",
          { message: latestUserText(input), user_token: token, thread_id: input.threadId },
          controller.signal,
        );
        for await (const item of stream) {
          for (const event of adkToAgui(item)) {
            subscriber.next(event);
            if (event.type === EventType.RUN_ERROR) return subscriber.complete();
          }
        }
        subscriber.next({ type: EventType.RUN_FINISHED, ...ids } as BaseEvent);
        subscriber.complete();
      })().catch((error: unknown) => {
        if (controller.signal.aborted) return subscriber.complete();
        console.error("Agent Runtime run failed:", error instanceof Error ? error.message : typeof error);
        subscriber.next({ type: EventType.RUN_ERROR, message: "The agent run failed. Please try again.", code: "internal" } as BaseEvent);
        subscriber.complete();
      });
      return () => controller.abort();
    });
  }

  abortRun(): void {
    this.controller?.abort();
    super.abortRun();
  }

  clone(): AgentRuntimeAgent {
    const copy = new AgentRuntimeAgent(this.client);
    copy.headers = { ...this.headers };
    return copy;
  }
}
