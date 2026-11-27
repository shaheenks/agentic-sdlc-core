import assert from "node:assert/strict";
import { test } from "node:test";

import { AgentClient, EventsClient, McpClient } from "../lib/backends.ts";
import { ServiceTokens } from "../lib/gcp.ts";
import { backendSettings } from "../lib/settings.ts";

const USER = { id: "1001", email: "ada@example.test" };
const SETTINGS = {
  agentUrl: "https://europe-west3-aiplatform.googleapis.com/v1/projects/p/locations/europe-west3/reasoningEngines/1",
  agentAuth: "google",
  mcpUrl: "https://mcp.example.test",
  mcpAuth: "id_token",
} as const;
const TOKENS = { accessToken: async () => "access", idToken: async (aud: string) => `id-for:${aud}` };

type Seen = { url: string; init: RequestInit };
function recorder(response: () => Response) {
  const seen: Seen[] = [];
  const impl = (async (url: string, init: RequestInit) => {
    seen.push({ url, init });
    return response();
  }) as unknown as typeof fetch;
  return { seen, impl };
}

test("the agent runtime is called with this service's access token, for the named user", async () => {
  const { seen, impl } = recorder(() => Response.json({ output: { id: "42" } }));
  const client = new AgentClient(SETTINGS, TOKENS, impl);
  assert.deepEqual(await client.createSession(USER), { id: "42" });
  assert.equal(seen[0].url, `${SETTINGS.agentUrl}:query`);
  assert.equal((seen[0].init.headers as Record<string, string>).authorization, "Bearer access");
  assert.deepEqual(JSON.parse(String(seen[0].init.body)), {
    class_method: "async_create_session",
    input: { user_id: "1001", state: { sdlc_user_email: "ada@example.test" } },
  });
});

test("streamed items are parsed, with or without SSE framing", async () => {
  const body = 'data: {"a":1}\n\n{"b":2}\n: keep-alive\n\ndata: {"c":3}';
  const { seen, impl } = recorder(() => new Response(body));
  const items = [];
  for await (const item of new AgentClient(SETTINGS, TOKENS, impl).ask(USER, "42", "hi")) items.push(item);
  assert.deepEqual(items, [{ a: 1 }, { b: 2 }, { c: 3 }]);
  assert.equal(seen[0].url, `${SETTINGS.agentUrl}:streamQuery?alt=sse`);
  assert.deepEqual(JSON.parse(String(seen[0].init.body)).input, { user_id: "1001", session_id: "42", message: "hi" });
});

test("an error status fails without passing the body on", async () => {
  const { impl } = recorder(() => new Response("quoted request with secrets", { status: 500 }));
  await assert.rejects(new AgentClient(SETTINGS, TOKENS, impl).listSessions(USER), (e: Error) => !e.message.includes("secrets"));
});

test("user_agent_mcp gets the user and this service's ID token, and only /api", async () => {
  const { seen, impl } = recorder(() => Response.json({ artifacts: [] }));
  const mcp = new McpClient(SETTINGS, TOKENS, impl);
  assert.deepEqual(await mcp.call(USER, "GET", "/api/artifacts"), { status: 200, body: { artifacts: [] } });
  const headers = seen[0].init.headers as Record<string, string>;
  assert.equal(seen[0].url, "https://mcp.example.test/api/artifacts");
  assert.equal(headers.authorization, "Bearer id-for:https://mcp.example.test");
  assert.equal(headers["x-sdlc-user-id"], "1001");
  assert.equal(headers["x-sdlc-user-email"], "ada@example.test");
  await assert.rejects(mcp.call(USER, "POST", "/mcp"));
});

test("backend settings fail closed outside local", () => {
  const env = { SDLC_AGENT_URL: "http://a", SDLC_MCP_URL: "http://m" };
  assert.throws(() => backendSettings({}));
  assert.throws(() => backendSettings({ ...env, SDLC_ENV: "dev", SDLC_AGENT_AUTH: "none" }));
  assert.throws(() => backendSettings({ ...env, SDLC_ENV: "dev", SDLC_MCP_AUTH: "none" }));
  assert.equal(backendSettings({ ...env, SDLC_ENV: "local", SDLC_AGENT_AUTH: "none", SDLC_MCP_AUTH: "none" }).agentAuth, "none");
  assert.equal(backendSettings({ ...env, SDLC_ENV: "dev" }).mcpAuth, "id_token");
});

test("service tokens come from the metadata server and are cached", async () => {
  let calls = 0;
  const payload = Buffer.from(JSON.stringify({ exp: 4_000_000_000 })).toString("base64url");
  const impl = (async (url: string) => {
    calls++;
    return url.endsWith("/token") ? Response.json({ access_token: "a", expires_in: 3600 }) : new Response(`h.${payload}.s`);
  }) as unknown as typeof fetch;
  const tokens = new ServiceTokens(impl, "http://metadata");
  assert.equal(await tokens.accessToken(), "a");
  assert.equal(await tokens.accessToken(), "a");
  assert.equal(await tokens.idToken("aud"), `h.${payload}.s`);
  await tokens.idToken("aud");
  assert.equal(calls, 2);
});

test("the event gateway gets the user and an ID token for its own URL, at /simulate only", async () => {
  const { seen, impl } = recorder(() => Response.json({ matched: 1, delivery_id: "sim-1" }, { status: 202 }));
  const events = new EventsClient({ ...SETTINGS, eventsUrl: "https://gateway.example.test" }, TOKENS, impl);
  assert.equal(events.configured, true);
  const sent = await events.simulate(USER, "POST", { team: "payments" });
  assert.deepEqual(sent, { status: 202, body: { matched: 1, delivery_id: "sim-1" } });
  const headers = seen[0].init.headers as Record<string, string>;
  assert.equal(seen[0].url, "https://gateway.example.test/simulate");
  assert.equal(headers.authorization, "Bearer id-for:https://gateway.example.test");
  assert.equal(headers["x-sdlc-user-email"], "ada@example.test");
  assert.equal(new EventsClient(SETTINGS, TOKENS, impl).configured, false);
});

test("the event gateway's settings fail closed", () => {
  const base = { SDLC_AGENT_URL: "https://a", SDLC_MCP_URL: "https://m" };
  assert.equal(backendSettings(base).eventsUrl, "");
  assert.throws(() => backendSettings({ ...base, SDLC_EVENTS_URL: "https://g", SDLC_EVENTS_AUTH: "none" }));
  assert.throws(() => backendSettings({ ...base, SDLC_EVENTS_URL: "gateway" }));
  assert.equal(backendSettings({ ...base, SDLC_EVENTS_URL: "https://g/" }).eventsUrl, "https://g");
});
