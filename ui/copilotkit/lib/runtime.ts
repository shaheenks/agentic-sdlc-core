// CopilotKit runtime (server side): one AG-UI agent, the SDLC agent's /agui endpoint.
//
// - The user's Entra token arrives from oauth2-proxy as X-Forwarded-Access-Token and is forwarded
//   to /agui ONLY (allowlist mode: no cookies, no other headers). The agent re-validates it.
//   It never reaches browser JavaScript and is never logged or stored here.
// - No thread storage in this process (PassThroughAgentRunner).
// - SDLC_AGUI_URL is the agent's internal URL (docker network); never a public host.

import { HttpAgent } from "@ag-ui/client";
import { CopilotRuntime, createCopilotRuntimeHandler } from "@copilotkit/runtime/v2";

import { PassThroughAgentRunner } from "./runner.ts";

export const BASE_PATH = "/chat"; // next.config.ts basePath
export const RUNTIME_PATH = `${BASE_PATH}/api/copilotkit`;
export const TOKEN_HEADER = "x-forwarded-access-token";

export function aguiUrl(env: Record<string, string | undefined> = process.env): string {
  const url = env.SDLC_AGUI_URL;
  if (!url) throw new Error("SDLC_AGUI_URL is not set (the agent's internal /agui URL)");
  return url;
}

let handler: ((request: Request) => Promise<Response>) | undefined;

export function copilotHandler(): (request: Request) => Promise<Response> {
  if (!handler) {
    const runtime = new CopilotRuntime({
      agents: { default: new HttpAgent({ url: aguiUrl() }) },
      runner: new PassThroughAgentRunner(),
      forwardHeaders: { allow: [TOKEN_HEADER] },
    });
    handler = createCopilotRuntimeHandler({ runtime, basePath: RUNTIME_PATH });
  }
  return handler;
}
