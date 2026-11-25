// sdlc_ui's two backends, always called for one verified user (DEC-0010). No React: unit-tested in
// tests/backends.test.ts.
//
// - The agent runtime (user_agent on Agent Runtime): `:query` and `:streamQuery` with {class_method, input}; the
//   user is the `user_id` of every call, and the email goes into a session's state when it is created.
// - user_agent_mcp's HTTP API: the user in X-SDLC-User-Id / X-SDLC-User-Email, sdlc_ui proven by its ID token.
// Error bodies are never passed on or logged: they could quote the request.

import type { Tokens } from "./gcp.ts";
import type { User } from "./identity.ts";
import type { BackendSettings } from "./settings.ts";

export const EMAIL_KEY = "sdlc_user_email";
export const TITLE_KEY = "sdlc_title";
export const TEAM_KEY = "sdlc_team"; // a team chat: the team scope set at start (FR-KNOW-004)

export class BackendError extends Error {
  readonly status: number;

  constructor(what: string, status: number) {
    super(`${what} HTTP ${status}`);
    this.name = "BackendError";
    this.status = status;
  }
}

export class AgentClient {
  private readonly settings: BackendSettings;
  private readonly tokens: Tokens | null;
  private readonly fetchImpl: typeof fetch;

  constructor(settings: BackendSettings, tokens: Tokens | null, fetchImpl: typeof fetch = fetch) {
    this.settings = settings;
    this.tokens = tokens;
    this.fetchImpl = fetchImpl;
  }

  private async post(action: string, method: string, input: Record<string, unknown>, signal?: AbortSignal) {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (this.settings.agentAuth === "google") {
      if (!this.tokens) throw new Error("no credentials for the agent runtime");
      headers.authorization = `Bearer ${await this.tokens.accessToken()}`;
    }
    const response = await this.fetchImpl(`${this.settings.agentUrl}${action}`, {
      method: "POST",
      headers,
      body: JSON.stringify({ class_method: method, input }),
      cache: "no-store",
      signal,
    });
    if (!response.ok) throw new BackendError(`agent ${method}`, response.status);
    return response;
  }

  async query(method: string, input: Record<string, unknown>): Promise<unknown> {
    const body = (await (await this.post(":query", method, input)).json()) as { output?: unknown };
    return body.output;
  }

  /** A streaming method's items: one JSON value per line (SSE `data:` framing tolerated). */
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

  // Sessions, always for one user: another user's session is never found.

  createSession(user: User, team?: string): Promise<unknown> {
    const state: Record<string, string> = { [EMAIL_KEY]: user.email, ...(team ? { [TEAM_KEY]: team } : {}) };
    return this.query("async_create_session", { user_id: user.id, state });
  }

  listSessions(user: User): Promise<unknown> {
    return this.query("async_list_sessions", { user_id: user.id });
  }

  getSession(user: User, sessionId: string): Promise<unknown> {
    return this.query("async_get_session", { user_id: user.id, session_id: sessionId });
  }

  deleteSession(user: User, sessionId: string): Promise<unknown> {
    return this.query("async_delete_session", { user_id: user.id, session_id: sessionId });
  }

  /** A turn: the user's text, or the answer to a workflow question as ADK content (a function response). */
  ask(user: User, sessionId: string, message: string | object, signal?: AbortSignal): AsyncGenerator<unknown> {
    return this.stream("async_stream_query", { user_id: user.id, session_id: sessionId, message }, signal);
  }
}

function parseLine(line: string): unknown {
  const text = line.trim().replace(/^data:\s*/, "");
  if (!text || text.startsWith(":")) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    console.error("agent runtime: an unreadable stream line was skipped");
    return undefined;
  }
}

export class McpClient {
  private readonly settings: BackendSettings;
  private readonly tokens: Tokens | null;
  private readonly fetchImpl: typeof fetch;

  constructor(settings: BackendSettings, tokens: Tokens | null, fetchImpl: typeof fetch = fetch) {
    this.settings = settings;
    this.tokens = tokens;
    this.fetchImpl = fetchImpl;
  }

  /** One call to user_agent_mcp's /api for the user; returns its status and JSON body as they are. */
  async call(user: User, method: string, path: string, body?: unknown): Promise<{ status: number; body: unknown }> {
    if (!path.startsWith("/api/")) throw new Error("only user_agent_mcp's /api is reachable");
    const headers: Record<string, string> = {
      "x-sdlc-user-id": user.id,
      "x-sdlc-user-email": user.email,
      "x-sdlc-surface": "sdlc_ui", // read only in the local identity mode (trusted_header)
    };
    if (this.settings.mcpAuth === "id_token") {
      if (!this.tokens) throw new Error("no credentials for user_agent_mcp");
      headers.authorization = `Bearer ${await this.tokens.idToken(this.settings.mcpUrl)}`;
    }
    if (body !== undefined) headers["content-type"] = "application/json";
    const response = await this.fetchImpl(`${this.settings.mcpUrl}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
    let parsed: unknown = null;
    try {
      parsed = await response.json();
    } catch {
      parsed = null;
    }
    return { status: response.status, body: parsed };
  }
}
