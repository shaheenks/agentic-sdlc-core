// An AgentRunner that keeps nothing in this process (version-01 M5).
//
// CopilotKit's InMemoryAgentRunner stores every thread's events in one process-wide map keyed only
// by thread id, and `connect` replays them to whoever names the id. This server does not
// authenticate users itself (the agent does), so that store would let one user replay another
// user's conversation. This runner passes each run straight to the agent and stores nothing:
// conversation history lives in the agent's session store, which is per user (token oid).
// `connect` replays nothing; `stop` aborts an in-flight run of this process.

import type { AbstractAgent, BaseEvent } from "@ag-ui/client";
import {
  AgentRunner,
  type AgentRunnerConnectRequest,
  type AgentRunnerIsRunningRequest,
  type AgentRunnerRunRequest,
  type AgentRunnerStopRequest,
  finalizeRunEvents,
} from "@copilotkit/runtime/v2";
import { EMPTY, type Observable, ReplaySubject } from "rxjs";

type Active = { agent: AbstractAgent; runId: string; stopRequested: boolean };

export class PassThroughAgentRunner extends AgentRunner {
  private readonly active = new Map<string, Active>();

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

  connect(_request: AgentRunnerConnectRequest): Observable<BaseEvent> {
    return EMPTY; // nothing stored here: history comes from the agent, per user
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
