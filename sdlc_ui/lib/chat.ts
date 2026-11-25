// The chat (FR-AGT-005, FR-WFL-009): user_agent on the agent runtime, spoken to as AG-UI through CopilotKit's
// runtime. No React: unit-tested in tests/chat.test.ts.
//
// - The route handler verifies the user and writes them into USER_HEADERS, replacing anything the browser sent;
//   CopilotKit forwards only those headers (allowlist) to the agent object, which calls the runtime for that user.
// - A chat's ID is its runtime session's ID, created for the user before the first message (POST /api/chats), so
//   a chat can only be continued by the user it belongs to: the runtime does not find another user's session.
// - Nothing is stored in this process (no InMemoryAgentRunner: it replays any thread to whoever names it).
//   Opening a chat reads its history from the runtime as the same user and replays it as one MESSAGES_SNAPSHOT.

import { AbstractAgent, type BaseEvent, EventType, type RunAgentInput } from "@ag-ui/client";
import {
  AgentRunner,
  type AgentRunnerConnectRequest,
  type AgentRunnerIsRunningRequest,
  type AgentRunnerRunRequest,
  type AgentRunnerStopRequest,
  finalizeRunEvents,
} from "@copilotkit/runtime/v2";
import { EMPTY, Observable, ReplaySubject } from "rxjs";

import type { AgentClient } from "./backends.ts";
import { adkToAgui, CHAT_ID, failureEvents, historyMessages, turnInput } from "./events.ts";
import type { User } from "./identity.ts";

export const USER_HEADERS = { id: "x-sdlc-user-id", email: "x-sdlc-user-email" } as const;
const HISTORY_TIMEOUT_MS = 15_000;

function header(headers: Record<string, string> | undefined, name: string): string {
  for (const [key, value] of Object.entries(headers ?? {})) if (key.toLowerCase() === name) return value;
  return "";
}

export function userFromHeaders(headers: Record<string, string> | undefined): User | null {
  const id = header(headers, USER_HEADERS.id);
  const email = header(headers, USER_HEADERS.email);
  return id && email ? { id, email } : null;
}

/** An AG-UI agent backed by the runtime's `async_stream_query`, for the user in its headers. */
export class RuntimeAgent extends AbstractAgent {
  headers: Record<string, string> = {};
  private controller?: AbortController;
  private readonly client: AgentClient;

  constructor(client: AgentClient) {
    super();
    this.client = client;
  }

  run(input: RunAgentInput): Observable<BaseEvent> {
    const ids = { threadId: input.threadId, runId: input.runId };
    const user = userFromHeaders(this.headers);
    return new Observable<BaseEvent>((subscriber) => {
      const controller = new AbortController();
      this.controller = controller;
      subscriber.next({ type: EventType.RUN_STARTED, ...ids } as BaseEvent);
      const fail = (message: string, code: string) => {
        subscriber.next({ type: EventType.RUN_ERROR, message, code } as BaseEvent);
        subscriber.complete();
      };
      (async () => {
        if (!user) return fail("Sign-in required.", "unauthenticated");
        if (!CHAT_ID.test(input.threadId)) return fail("Unknown chat.", "not_found");
        const message = turnInput(input.messages as Parameters<typeof turnInput>[0]);
        // tool calls without a result yet: a failed run closes them, so no card stays "running"
        const open = new Set<string>();
        for await (const item of this.client.ask(user, input.threadId, message, controller.signal)) {
          for (const event of adkToAgui(item)) {
            if (event.type === EventType.RUN_ERROR) {
              console.error("agent run failed: the runtime reported an error");
              for (const closing of failureEvents([...open], item)) subscriber.next(closing);
              subscriber.next({ type: EventType.RUN_FINISHED, ...ids } as BaseEvent);
              return subscriber.complete();
            }
            const e = event as { type: string; toolCallId?: string };
            if (e.type === EventType.TOOL_CALL_START && e.toolCallId) open.add(e.toolCallId);
            if (e.type === EventType.TOOL_CALL_RESULT && e.toolCallId) open.delete(e.toolCallId);
            subscriber.next(event);
          }
        }
        subscriber.next({ type: EventType.RUN_FINISHED, ...ids } as BaseEvent);
        subscriber.complete();
      })().catch((error: unknown) => {
        if (controller.signal.aborted) return subscriber.complete();
        console.error("agent run failed:", error instanceof Error ? error.message : typeof error);
        fail("The agent run failed. Please try again.", "internal");
      });
      return () => controller.abort();
    });
  }

  abortRun(): void {
    this.controller?.abort();
    super.abortRun();
  }

  clone(): RuntimeAgent {
    const copy = new RuntimeAgent(this.client);
    copy.headers = { ...this.headers };
    return copy;
  }
}

type Active = { agent: AbstractAgent; runId: string; stopRequested: boolean };

/** Runs pass straight through; history is read from the runtime for the requesting user. */
export class PassThroughRunner extends AgentRunner {
  private readonly active = new Map<string, Active>();
  private readonly client: Pick<AgentClient, "getSession">;

  constructor(client: Pick<AgentClient, "getSession">) {
    super();
    this.client = client;
  }

  run(request: AgentRunnerRunRequest): Observable<BaseEvent> {
    const subject = new ReplaySubject<BaseEvent>(Infinity);
    const events: BaseEvent[] = [];
    const entry: Active = { agent: request.agent, runId: request.input.runId, stopRequested: false };
    this.active.set(request.threadId, entry);
    const finish = (interruptionMessage?: string) => {
      const closing = finalizeRunEvents(events, {
        stopRequested: entry.stopRequested,
        protocolVersion: request.input.protocolVersion,
        ...(interruptionMessage !== undefined ? { interruptionMessage } : {}),
      });
      for (const event of closing) subject.next(event);
      subject.complete();
      if (this.active.get(request.threadId) === entry) this.active.delete(request.threadId);
    };
    request.agent
      .runAgent(request.input, {
        onEvent: ({ event }: { event: BaseEvent }) => {
          events.push(event);
          subject.next(event);
        },
      })
      .then(() => finish())
      .catch((error: unknown) => {
        console.error("agent run failed:", error instanceof Error ? error.name : typeof error);
        finish("The agent run failed. Please try again.");
      });
    return subject.asObservable();
  }

  connect(request: AgentRunnerConnectRequest): Observable<BaseEvent> {
    const user = userFromHeaders(request.headers);
    if (!user || !CHAT_ID.test(request.threadId)) return EMPTY;
    return new Observable<BaseEvent>((subscriber) => {
      const timer = setTimeout(() => subscriber.complete(), HISTORY_TIMEOUT_MS);
      this.client
        .getSession(user, request.threadId)
        .then((session) => {
          const messages = historyMessages(session);
          if (messages.length) {
            const ids = { threadId: request.threadId, runId: `history-${crypto.randomUUID()}` };
            subscriber.next({ type: EventType.RUN_STARTED, ...ids } as BaseEvent);
            subscriber.next({ type: EventType.MESSAGES_SNAPSHOT, messages } as BaseEvent);
            subscriber.next({ type: EventType.RUN_FINISHED, ...ids } as BaseEvent);
          }
          subscriber.complete();
        })
        .catch((error: unknown) => {
          // not this user's chat, or unreadable: open it empty; no details (they could carry data)
          console.error("history load failed:", error instanceof Error ? error.name : typeof error);
          subscriber.complete();
        })
        .finally(() => clearTimeout(timer));
      return () => clearTimeout(timer);
    });
  }

  async isRunning(request: AgentRunnerIsRunningRequest): Promise<boolean> {
    return this.active.has(request.threadId);
  }

  async stop(request: AgentRunnerStopRequest): Promise<boolean | undefined> {
    const entry = this.active.get(request.threadId);
    if (!entry || (request.runId && request.runId !== entry.runId)) return false;
    entry.stopRequested = true;
    entry.agent.abortRun();
    return true;
  }
}
