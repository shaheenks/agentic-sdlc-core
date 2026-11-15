// The native stack's same-origin APIs (CH-0016): each acts only after the IAP + session check, and
// forwards only the verified user token (plus the UI's own identity to Cloud Run IAM).

import assert from "node:assert/strict";
import { test } from "node:test";

import { me, mcpSettings, proxyToMcp, threads } from "../lib/native-api.ts";
import { SESSION_COOKIE, seal } from "../lib/session.ts";
import { DOMAIN, deps, iapAssertion, idToken, signIn } from "./fake-google.ts";

const ALICE_TOKEN = idToken("111");

function request(path: string, init: RequestInit & { session?: boolean } = {}): Request {
  const headers = new Headers(init.headers);
  headers.set("x-goog-iap-jwt-assertion", iapAssertion("111"));
  if (init.session !== false) {
    headers.set("cookie", `${SESSION_COOKIE}=${seal({ v: 1, iapSub: "111", idToken: ALICE_TOKEN, refreshToken: "r" }, signIn.key)}`);
  }
  return new Request(`https://ui.example.test${path}`, { ...init, headers });
}

test("/me answers with the verified name and sign-in name only", async () => {
  const response = await me(request("/me"), deps());
  assert.deepEqual(await response.json(), { name: "Alice", upn: `alice@${DOMAIN}` });
  const none = await me(request("/me", { session: false }), deps());
  assert.equal(none.status, 401);
  assert.deepEqual(await none.json(), { error: "sign_in_required", signIn: "/chat/auth/start" });
});

test("/threads lists and deletes as the user; refusals map to HTTP", async () => {
  const seen: [string, Record<string, unknown>][] = [];
  const engine = {
    query: async (method: string, input: Record<string, unknown>) => {
      seen.push([method, input]);
      if (method === "list_threads") return [{ threadId: "t1", title: "Hi", updatedAt: "2026-11-15T00:00:00Z" }];
      return input.session_id === "t1" ? { deleted: true } : { refusal: { code: "not_found", message: "conversation not found" } };
    },
  };
  const list = await threads(request("/threads"), engine, undefined, deps());
  assert.deepEqual((await list.json()).threads[0].threadId, "t1");
  assert.deepEqual(seen[0], ["list_threads", { user_token: ALICE_TOKEN }]);
  const del = await threads(request("/threads/t1", { method: "DELETE", headers: { "X-SDLC-Request": "1" } }), engine, "t1", deps());
  assert.equal(del.status, 200);
  assert.deepEqual(seen[1], ["delete_thread", { user_token: ALICE_TOKEN, session_id: "t1" }]);
  const other = await threads(request("/threads/t9", { method: "DELETE", headers: { "X-SDLC-Request": "1" } }), engine, "t9", deps());
  assert.equal(other.status, 404);
  const noHeader = await threads(request("/threads/t1", { method: "DELETE" }), engine, "t1", deps());
  assert.equal(noHeader.status, 403);
  const signedOut = await threads(request("/threads", { session: false }), engine, undefined, deps());
  assert.equal(signedOut.status, 401);
  assert.equal(seen.length, 3); // nothing called without a verified user
});

test("an engine refusal of the token asks for sign-in", async () => {
  const engine = { query: async () => ({ refusal: { code: "unauthenticated", message: "x" } }) };
  const response = await threads(request("/threads"), engine, undefined, deps());
  assert.equal(response.status, 401);
});

test("/connections and /artifacts go to sdlc-mcp-native with the user's and the UI's tokens only", async () => {
  const seen: { url: string; headers: Headers; method: string }[] = [];
  const fetchImpl = (async (url: string, init: RequestInit) => {
    seen.push({ url, headers: new Headers(init.headers), method: init.method ?? "GET" });
    return new Response("file body", {
      status: 200,
      headers: { "content-type": "text/markdown", "content-disposition": "attachment; filename=a.md", "set-cookie": "x=1", server: "mcp" },
    });
  }) as unknown as typeof fetch;
  const tokens = { idToken: async (aud: string) => `ui-id-token-for-${aud}` };
  const mcp = mcpSettings({ SDLC_MCP_BASE_URL: "https://mcp.example.test/" });
  const browser = request("/artifacts/abc?version=2", { headers: { authorization: "Bearer forged", cookie: "evil=1", accept: "text/markdown" } });
  // the cookie header from the browser is replaced by request(); add it back with the session
  const response = await proxyToMcp(browser, ["artifacts", "abc"], mcp, tokens, fetchImpl, deps());
  assert.equal(await response.text(), "file body");
  assert.equal(seen[0].url, "https://mcp.example.test/artifacts/abc?version=2");
  assert.equal(seen[0].headers.get("authorization"), `Bearer ${ALICE_TOKEN}`);
  assert.equal(seen[0].headers.get("x-serverless-authorization"), "Bearer ui-id-token-for-https://mcp.example.test");
  assert.equal(seen[0].headers.get("cookie"), null);
  assert.equal(seen[0].headers.get("accept"), "text/markdown");
  assert.equal(response.headers.get("content-disposition"), "attachment; filename=a.md");
  assert.equal(response.headers.get("set-cookie"), null);
  assert.equal(response.headers.get("server"), null);

  await proxyToMcp(request("/connections/"), ["connections"], mcp, tokens, fetchImpl, deps());
  assert.equal(seen[1].url, "https://mcp.example.test/connections/");
});

test("only the two MCP roots are reachable, and only for a verified user", async () => {
  let called = 0;
  const fetchImpl = (async () => {
    called++;
    return new Response("");
  }) as unknown as typeof fetch;
  const tokens = { idToken: async () => "t" };
  const mcp = { baseUrl: "https://mcp.example.test" };
  for (const path of [["mcp"], ["healthz"], ["artifacts", ".."], []]) {
    assert.equal((await proxyToMcp(request("/x"), path, mcp, tokens, fetchImpl, deps())).status, 404, path.join("/"));
  }
  assert.equal((await proxyToMcp(request("/artifacts/", { session: false }), ["artifacts"], mcp, tokens, fetchImpl, deps())).status, 401);
  assert.equal(called, 0);
  assert.throws(() => mcpSettings({ SDLC_MCP_BASE_URL: "http://mcp" }), /SDLC_MCP_BASE_URL/);
});
