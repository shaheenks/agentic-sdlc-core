// An AgentRunner that keeps nothing in this process (version-01 M5).
//
// CopilotKit's InMemoryAgentRunner stores every thread's events in one process-wide map keyed only
// by thread id, and `connect` replays them to whoever names the id. This server does not
// authenticate users itself (the agent does), so that store would let one user replay another
// user's conversation. This runner passes each run straight to the agent and stores nothing:
// conversation history lives in the agent's session store, which is per user (token oid).
// `connect` (opening a thread, version-02 N15) asks the agent for that thread's messages as the
// same user (the forwarded token, nothing else) and replays them as one MESSAGES_SNAPSHOT; without
// a token or a history URL it replays nothing. `stop` aborts an in-flight run of this process.

import { type AbstractAgent, type BaseEvent, EventType } from "@ag-ui/client";
import {
  AgentRunner,
  type AgentRunnerConnectRequest,
  type AgentRunnerIsRunningRequest,
  type AgentRunnerRunRequest,
  type AgentRunnerStopRequest,
  finalizeRunEvents,
} from "@copilotkit/runtime/v2";
import { EMPTY, Observable, ReplaySubject } from "rxjs";

import { historyMessages, THREAD_ID } from "./threads.ts";

export const TOKEN_HEADER = "x-forwarded-access-token";
const HISTORY_TIMEOUT_MS = 15_000;

type Active = { agent: AbstractAgent; runId: string; stopRequested: boolean };

function headerValue(headers: Record<string, string> | undefined, name: string): string {
  for (const [key, value] of Object.entries(headers ?? {})) {
    if (key.toLowerCase() === name) return value;
  }
  return "";
}

export class PassThroughAgentRunner extends AgentRunner {
  private readonly active = new Map<string, Active>();

  private readonly historyUrl: string | undefined;
  private readonly fetchImpl: typeof fetch;

  /** @param historyUrl the agent's /agents/state URL (internal); unset = no history replay */
  constructor(historyUrl?: string, fetchImpl: typeof fetch = fetch) {
    super();
    this.historyUrl = historyUrl;
    this.fetchImpl = fetchImpl;
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
        // never forward error details that could carry request data; the agent logs them
        console.error("agent run failed:", error instanceof Error ? error.name : typeof error);
        finish("The agent run failed. Please try again.");
      });

    return subject.asObservable();
  }

  connect(request: AgentRunnerConnectRequest): Observable<BaseEvent> {
    // nothing stored here: history comes from the agent, for the user the token names
    const token = headerValue(request.headers, TOKEN_HEADER);
    if (!this.historyUrl || !token || !THREAD_ID.test(request.threadId)) return EMPTY;
    const { historyUrl, fetchImpl } = this;
    return new Observable<BaseEvent>((subscriber) => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), HISTORY_TIMEOUT_MS);
      fetchImpl(historyUrl, {
        method: "POST",
        headers: { "content-type": "application/json", [TOKEN_HEADER]: token },
        body: JSON.stringify({ threadId: request.threadId }),
        signal: controller.signal,
      })
        .then(async (response) => (response.ok ? historyMessages(await response.json()) : []))
        .then((messages) => {
          if (messages.length > 0) {
            const ids = { threadId: request.threadId, runId: `history-${crypto.randomUUID()}` };
            subscriber.next({ type: EventType.RUN_STARTED, ...ids } as BaseEvent);
            subscriber.next({ type: EventType.MESSAGES_SNAPSHOT, messages } as BaseEvent);
            subscriber.next({ type: EventType.RUN_FINISHED, ...ids } as BaseEvent);
          }
          subscriber.complete();
        })
        .catch((error: unknown) => {
          // an unreadable history opens an empty thread; no details (they could carry data)
          console.error("history load failed:", error instanceof Error ? error.name : typeof error);
          subscriber.complete();
        })
        .finally(() => clearTimeout(timer));
      return () => {
        clearTimeout(timer);
        controller.abort();
      };
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
