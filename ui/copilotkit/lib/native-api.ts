// The native stack's same-origin APIs (CH-0016), in place of oauth2-proxy's upstreams:
// /me, /threads (Agent Runtime) and /connections/*, /artifacts/* (sdlc-mcp-native). Each one runs
// `resolveUser` first and forwards only the user's verified Google ID token. No React:
// unit-tested in tests/native-api.test.ts.

import { type EngineClient, refusalOf } from "./agent-runtime.ts";
import type { ServiceTokens } from "./gcp.ts";
import { type NativeDeps, nativeDeps, refusal, resolveUser, withSession } from "./native.ts";
import { SIGN_IN_PATH } from "./session.ts";
import { THREAD_ID } from "./threads.ts";

const json = (body: unknown, status = 200) =>
  Response.json(body, { status, headers: { "cache-control": "no-store" } });

function engineRefusal(output: unknown): Response | null {
  const r = refusalOf(output);
  if (!r) return null;
  if (r.code === "unauthenticated") return json({ error: "sign_in_required", signIn: SIGN_IN_PATH }, 401);
  if (r.code === "not_found") return json({ error: "not_found" }, 404);
  return json({ error: r.code, message: r.message }, r.code === "invalid_argument" ? 400 : 502);
}

/** GET /me: the caller's display name and sign-in name (nothing else). */
export async function me(request: Request, d: NativeDeps = nativeDeps()): Promise<Response> {
  const r = await resolveUser(request, d);
  if (!r.ok) return refusal(r);
  return withSession(json({ name: r.user.name || r.user.email, upn: r.user.email }), r);
}

/** GET /threads: the caller's conversations; DELETE /threads/<id>: delete one. */
export async function threads(
  request: Request,
  engine: Pick<EngineClient, "query">,
  id?: string,
  d: NativeDeps = nativeDeps(),
): Promise<Response> {
  const r = await resolveUser(request, d);
  if (!r.ok) return refusal(r);
  try {
    if (id === undefined) {
      const output = await engine.query("list_threads", { user_token: r.idToken });
      return withSession(engineRefusal(output) ?? json({ threads: Array.isArray(output) ? output : [] }), r);
    }
    // a cross-site page cannot send this header without a CORS preflight (as the agent's route)
    if (request.headers.get("x-sdlc-request") !== "1") return json({ error: "missing X-SDLC-Request" }, 403);
    if (!THREAD_ID.test(id)) return json({ error: "not_found" }, 404);
    const output = await engine.query("delete_thread", { user_token: r.idToken, session_id: id });
    return withSession(engineRefusal(output) ?? json({ deleted: true }), r);
  } catch (e) {
    console.error("threads call failed:", e instanceof Error ? e.message : typeof e);
    return json({ error: "agent_unavailable" }, 502);
  }
}

const MCP_ROOTS = new Set(["connections", "artifacts"]);
const FORWARD_REQUEST = ["content-type", "accept", "x-sdlc-request", "if-none-match"];
const FORWARD_RESPONSE = ["content-type", "content-disposition", "cache-control", "etag", "x-content-type-options"];

export type McpSettings = { baseUrl: string }; // https://<sdlc-mcp-native host>, also the IAM audience

export function mcpSettings(env: Record<string, string | undefined> = process.env): McpSettings {
  const baseUrl = (env.SDLC_MCP_BASE_URL ?? "").replace(/\/+$/, "");
  if (!baseUrl.startsWith("https://")) throw new Error("SDLC_MCP_BASE_URL must be the https URL of sdlc-mcp-native");
  return { baseUrl };
}

/**
 * /connections/* and /artifacts/* -> sdlc-mcp-native: the user's ID token in Authorization (the
 * server decides per user), the UI service account's ID token in X-Serverless-Authorization
 * (Cloud Run IAM). Nothing else the browser sent is passed on except a few content headers.
 */
export async function proxyToMcp(
  request: Request,
  path: string[],
  mcp: McpSettings,
  tokens: Pick<ServiceTokens, "idToken">,
  fetchImpl: typeof fetch = fetch,
  d: NativeDeps = nativeDeps(),
): Promise<Response> {
  if (!path.length || !MCP_ROOTS.has(path[0]) || path.some((p) => !p || p === "." || p === ".." || p.includes("/"))) {
    return json({ error: "not_found" }, 404);
  }
  const r = await resolveUser(request, d);
  if (!r.ok) return refusal(r);
  const source = new URL(request.url);
  const target = `${mcp.baseUrl}/${path.map(encodeURIComponent).join("/")}${path.length === 1 ? "/" : ""}${source.search}`;
  const headers = new Headers();
  for (const name of FORWARD_REQUEST) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("authorization", `Bearer ${r.idToken}`);
  try {
    headers.set("x-serverless-authorization", `Bearer ${await tokens.idToken(mcp.baseUrl)}`);
    const hasBody = request.method !== "GET" && request.method !== "HEAD";
    const response = await fetchImpl(target, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      cache: "no-store",
      redirect: "manual",
      ...(hasBody ? { duplex: "half" } : {}),
    } as RequestInit);
    const out = new Headers();
    for (const name of FORWARD_RESPONSE) {
      const value = response.headers.get(name);
      if (value) out.set(name, value);
    }
    return withSession(new Response(response.body, { status: response.status, headers: out }), r);
  } catch (e) {
    console.error("MCP proxy call failed:", e instanceof Error ? e.message : typeof e);
    return json({ error: "mcp_unavailable" }, 502);
  }
}
