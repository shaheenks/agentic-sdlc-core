// The BFF's per-process parts and the guard every API route goes through. Server only.
//
// `withUser` verifies the user (lib/identity.ts) before anything else and refuses with 401 otherwise; handlers
// get the verified user and never read identity from the request themselves.

import { CopilotRuntime, createCopilotRuntimeHandler } from "@copilotkit/runtime/v2";

import { AgentClient, McpClient } from "./backends.ts";
import { PassThroughRunner, RuntimeAgent, USER_HEADERS } from "./chat.ts";
import { ServiceTokens } from "./gcp.ts";
import { authSettings, type User, userOf } from "./identity.ts";
import { backendSettings } from "./settings.ts";

export const RUNTIME_PATH = "/api/copilotkit";

type Parts = { agent: AgentClient; mcp: McpClient; copilot: (request: Request) => Promise<Response> };
let parts: Parts | undefined;

export function backends(): Parts {
  if (!parts) {
    const settings = backendSettings();
    const tokens = settings.agentAuth === "none" && settings.mcpAuth === "none" ? null : new ServiceTokens();
    const agent = new AgentClient(settings, tokens);
    const runtime = new CopilotRuntime({
      agents: { default: new RuntimeAgent(agent) },
      runner: new PassThroughRunner(agent),
      forwardHeaders: { allow: [USER_HEADERS.id, USER_HEADERS.email] },
    });
    parts = { agent, mcp: new McpClient(settings, tokens), copilot: createCopilotRuntimeHandler({ runtime, basePath: RUNTIME_PATH }) };
  }
  return parts;
}

export function json(body: unknown, status = 200): Response {
  return Response.json(body, { status, headers: { "cache-control": "no-store" } });
}

export async function withUser(request: Request, handle: (user: User) => Promise<Response>): Promise<Response> {
  let user: User;
  try {
    user = await userOf(request.headers, authSettings());
  } catch (error) {
    console.error("sign-in refused:", error instanceof Error ? error.message : typeof error);
    return json({ error: "unauthenticated", message: "Sign-in required." }, 401);
  }
  try {
    return await handle(user);
  } catch (error) {
    console.error("request failed:", error instanceof Error ? error.message : typeof error);
    return json({ error: "unavailable", message: "Something went wrong. Please try again." }, 502);
  }
}

/** A request for the CopilotKit runtime with the verified user in its headers, replacing what the browser sent. */
export function asUser(request: Request, user: User): Request {
  const headers = new Headers(request.headers);
  headers.set(USER_HEADERS.id, user.id);
  headers.set(USER_HEADERS.email, user.email);
  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  return new Request(request.url, {
    method: request.method,
    headers,
    body: hasBody ? request.body : undefined,
    signal: request.signal,
    ...(hasBody ? { duplex: "half" } : {}),
  } as RequestInit);
}
