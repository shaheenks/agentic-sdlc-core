// CopilotKit runtime (server side): one AG-UI agent, from one of two backends (SDLC_AGENT_BACKEND).
//
// - `agui` (default; local compose and the Entra stack): the SDLC agent's /agui endpoint. The
//   user's token arrives from oauth2-proxy as X-Forwarded-Access-Token.
// - `agent-runtime` (the native GCP stack, CH-0016): the user agent on Agent Runtime
//   (lib/agent-runtime.ts). The route handler verifies IAP and the session first and writes the
//   user's Google ID token into the same header (lib/native.ts); anything the client sent there
//   is replaced.
// Either way the token is forwarded to the agent ONLY (allowlist mode: no cookies, no other
// headers) and re-validated there. It never reaches browser JavaScript and is never logged or
// stored here. No thread storage in this process (PassThroughAgentRunner): opening a previous
// thread replays it from the agent as the same user.

import { HttpAgent } from "@ag-ui/client";
import { CopilotRuntime, createCopilotRuntimeHandler } from "@copilotkit/runtime/v2";

import { AgentRuntimeAgent, EngineClient, engineSettings, refusalOf } from "./agent-runtime.ts";
import { ServiceTokens } from "./gcp.ts";
import { type HistoryLoader, PassThroughAgentRunner, TOKEN_HEADER } from "./runner.ts";

export { TOKEN_HEADER };
export const BASE_PATH = "/chat"; // next.config.ts basePath
export const RUNTIME_PATH = `${BASE_PATH}/api/copilotkit`;

export function aguiUrl(env: Record<string, string | undefined> = process.env): string {
  const url = env.SDLC_AGUI_URL;
  if (!url) throw new Error("SDLC_AGUI_URL is not set (the agent's internal /agui URL)");
  return url;
}

/** The agent's thread history endpoint (ag_ui_adk), next to /agui on the same internal host. */
export function historyUrl(env: Record<string, string | undefined> = process.env): string {
  return new URL("/agents/state", aguiUrl(env)).toString();
}

let engine: EngineClient | undefined;
/** The Agent Runtime client of the native stack (one per process). */
export function engineClient(): EngineClient {
  engine ??= new EngineClient(engineSettings(), new ServiceTokens());
  return engine;
}

/** History from `get_thread`, in the /agents/state shape the runner already reads. */
export function engineHistory(client: Pick<EngineClient, "query">): HistoryLoader {
  return async (threadId, token) => {
    const output = await client.query("get_thread", { user_token: token, thread_id: threadId });
    if (refusalOf(output)) return { threadExists: false, messages: [] };
    const messages = (output as { messages?: unknown })?.messages;
    return { threadExists: Array.isArray(messages), messages: Array.isArray(messages) ? messages : [] };
  };
}

let handler: ((request: Request) => Promise<Response>) | undefined;

export function copilotHandler(env: Record<string, string | undefined> = process.env): (request: Request) => Promise<Response> {
  if (!handler) {
    const native = env.SDLC_AGENT_BACKEND === "agent-runtime";
    const runtime = new CopilotRuntime({
      agents: { default: native ? new AgentRuntimeAgent(engineClient()) : new HttpAgent({ url: aguiUrl(env) }) },
      runner: new PassThroughAgentRunner(native ? engineHistory(engineClient()) : historyUrl(env)),
      forwardHeaders: { allow: [TOKEN_HEADER] },
    });
    handler = createCopilotRuntimeHandler({ runtime, basePath: RUNTIME_PATH });
  }
  return handler;
}
