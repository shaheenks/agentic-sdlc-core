// The native stack's server-side sign-in (CH-0016): sealed cookies bound to the IAP user, a silent
// code flow, renewal, and every request checked before a token is forwarded.

import assert from "node:assert/strict";
import { test } from "node:test";

import { finishSignIn, IAP_SIGN_OUT, signOut, startSignIn } from "../lib/auth-routes.ts";
import { resolveUser } from "../lib/native.ts";
import {
  authorizationUrl,
  FLOW_COOKIE,
  type Flow,
  newFlow,
  readCookie,
  SESSION_COOKIE,
  type Session,
  safeReturnTo,
  seal,
  signInSettings,
  unseal,
} from "../lib/session.ts";
import { CLIENT, DOMAIN, deps, iapAssertion, idToken, NOW, signIn } from "./fake-google.ts";

const ORIGIN = signIn.publicUrl;

function request(path: string, opts: { iap?: string | null; cookies?: Record<string, string> } = {}): Request {
  const headers = new Headers();
  const iap = opts.iap === undefined ? iapAssertion("111") : opts.iap;
  if (iap) headers.set("x-goog-iap-jwt-assertion", iap);
  const cookies = Object.entries(opts.cookies ?? {}).map(([k, v]) => `${k}=${v}`);
  if (cookies.length) headers.set("cookie", cookies.join("; "));
  return new Request(`${ORIGIN}${path}`, { headers });
}

const sessionCookie = (session: Partial<Session> = {}) =>
  seal({ v: 1, iapSub: "111", idToken: idToken("111"), refreshToken: "refresh-1", ...session }, signIn.key);

function setCookies(response: Response): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of response.headers.getSetCookie()) {
    const [pair] = line.split(";");
    const [name, ...value] = pair.split("=");
    out[name] = value.join("=");
    assert.match(line, /; Path=\/; Secure; HttpOnly; SameSite=Lax; Max-Age=\d+$/, name);
  }
  return out;
}

// --- sealing ---------------------------------------------------------------------------------

test("a sealed value opens only unchanged and with the same key", () => {
  const sealed = seal({ a: 1 }, signIn.key);
  assert.deepEqual(unseal(sealed, signIn.key), { a: 1 });
  assert.equal(unseal(sealed, Buffer.alloc(32, 9)), null);
  const tampered = `${sealed.slice(0, -2)}${sealed.endsWith("A") ? "B" : "A"}A`;
  assert.equal(unseal(tampered, signIn.key), null);
  assert.equal(unseal("not-sealed", signIn.key), null);
  assert.equal(unseal(undefined, signIn.key), null);
});

test("only same-site paths are returned to", () => {
  assert.equal(safeReturnTo("/chat/?thread=t1"), "/chat/?thread=t1");
  for (const bad of ["https://evil.test/", "//evil.test", "/\\evil.test", "", null]) assert.equal(safeReturnTo(bad), "/chat/");
});

test("sign-in settings are required and the key must be 32 bytes", () => {
  assert.throws(() => signInSettings({}), /must be set/);
  const env = {
    SDLC_GOOGLE_WEB_CLIENT_ID: CLIENT,
    SDLC_GOOGLE_WEB_CLIENT_SECRET: "s",
    SDLC_PUBLIC_URL: "https://ui.example.test/",
    SDLC_SESSION_KEY: Buffer.alloc(32, 1).toString("base64url"),
  };
  assert.equal(signInSettings(env).publicUrl, "https://ui.example.test");
  assert.throws(() => signInSettings({ ...env, SDLC_PUBLIC_URL: "http://ui.example.test" }), /must be set/);
  assert.throws(() => signInSettings({ ...env, SDLC_SESSION_KEY: "c2hvcnQ" }), /must be set/);
});

// --- the code flow ---------------------------------------------------------------------------

test("the authorization request is silent, offline, PKCE and for the IAP user", () => {
  const flow = newFlow("111", "/chat/", false);
  const url = new URL(authorizationUrl(flow, signIn, `alice@${DOMAIN}`));
  const q = url.searchParams;
  assert.equal(url.origin + url.pathname, "https://accounts.google.com/o/oauth2/v2/auth");
  assert.equal(q.get("client_id"), CLIENT);
  assert.equal(q.get("redirect_uri"), `${ORIGIN}/chat/auth/callback`);
  assert.equal(q.get("prompt"), "none");
  assert.equal(q.get("access_type"), "offline");
  assert.equal(q.get("login_hint"), `alice@${DOMAIN}`);
  assert.equal(q.get("code_challenge_method"), "S256");
  assert.equal(q.get("state"), flow.state);
  assert.notEqual(q.get("code_challenge"), flow.verifier);
  assert.equal(new URL(authorizationUrl(newFlow("111", "/", true), signIn, "x")).searchParams.get("prompt"), "consent");
});

test("start needs IAP and sets a sealed flow cookie", async () => {
  assert.equal((await startSignIn(request("/chat/auth/start", { iap: null }), deps())).status, 401);
  const response = await startSignIn(request("/chat/auth/start?returnTo=%2Fchat%2F%3Fthread%3Dt1"), deps());
  assert.equal(response.status, 302);
  assert.match(response.headers.get("location") ?? "", /^https:\/\/accounts\.google\.com\//);
  const flow = unseal<Flow>(setCookies(response)[FLOW_COOKIE], signIn.key);
  assert.equal(flow?.iapSub, "111");
  assert.equal(flow?.returnTo, "/chat/?thread=t1");
});

function tokenEndpoint(body: Record<string, unknown>, seen: URLSearchParams[] = []): typeof fetch {
  return (async (_url: string, init?: RequestInit) => {
    seen.push(new URLSearchParams(String(init?.body)));
    return Response.json(body);
  }) as unknown as typeof fetch;
}

async function callback(flow: Flow, query: string, token: Record<string, unknown>, iapSub = "111") {
  const seen: URLSearchParams[] = [];
  const response = await finishSignIn(
    request(`/chat/auth/callback?${query}`, {
      iap: iapAssertion(iapSub, iapSub === "111" ? `alice@${DOMAIN}` : `bob@${DOMAIN}`),
      cookies: { [FLOW_COOKIE]: seal(flow, signIn.key) },
    }),
    deps(tokenEndpoint(token, seen)),
  );
  return { response, seen };
}

test("the callback starts a session bound to the IAP user and returns to the chat", async () => {
  const flow = newFlow("111", "/chat/?thread=t1", false);
  const { response, seen } = await callback(flow, `state=${flow.state}&code=c1`, { id_token: idToken("111"), refresh_token: "r1" });
  assert.equal(response.status, 302);
  assert.equal(response.headers.get("location"), `${ORIGIN}/chat/?thread=t1`);
  assert.equal(seen[0].get("code_verifier"), flow.verifier);
  assert.equal(seen[0].get("grant_type"), "authorization_code");
  const session = unseal<Session>(setCookies(response)[SESSION_COOKIE], signIn.key);
  assert.equal(session?.iapSub, "111");
  assert.equal(session?.refreshToken, "r1");
});

test("the callback refuses another state, another IAP user or another Google account", async () => {
  const flow = newFlow("111", "/chat/", false);
  const token = { id_token: idToken("111"), refresh_token: "r1" };
  assert.equal((await callback(flow, "state=other&code=c1", token)).response.status, 400);
  assert.equal((await callback(flow, `state=${flow.state}&code=c1`, token, "222")).response.status, 400);
  const bob = { id_token: idToken("222", `bob@${DOMAIN}`), refresh_token: "r1" };
  const refused = await callback(flow, `state=${flow.state}&code=c1`, bob);
  assert.equal(refused.response.status, 403);
  assert.equal(setCookies(refused.response)[SESSION_COOKIE], undefined);
  const outsider = { id_token: idToken("111", undefined, { hd: "elsewhere.test" }) };
  assert.equal((await callback(flow, `state=${flow.state}&code=c1`, outsider)).response.status, 403);
});

test("without a refresh token, or when Google needs a prompt, sign-in asks once with consent", async () => {
  const flow = newFlow("111", "/chat/", false);
  const noRefresh = await callback(flow, `state=${flow.state}&code=c1`, { id_token: idToken("111") });
  assert.match(noRefresh.response.headers.get("location") ?? "", /\/chat\/auth\/start\?.*consent=1/);
  const prompt = await callback(flow, `state=${flow.state}&error=interaction_required`, {});
  assert.match(prompt.response.headers.get("location") ?? "", /consent=1/);
  const consented = newFlow("111", "/chat/", true);
  const again = await callback(consented, `state=${consented.state}&error=access_denied`, {});
  assert.equal(again.response.status, 403); // no loop
});

test("sign-out drops the session and IAP's login", () => {
  const response = signOut();
  assert.equal(response.headers.get("location"), IAP_SIGN_OUT);
  assert.equal(setCookies(response)[SESSION_COOKIE], "");
});

// --- every request ---------------------------------------------------------------------------

test("a request with IAP and its own session forwards that user's token", async () => {
  const r = await resolveUser(request("/chat/api/copilotkit", { cookies: { [SESSION_COOKIE]: sessionCookie() } }), deps());
  assert.equal(r.ok, true);
  if (r.ok) {
    assert.equal(r.user.email, `alice@${DOMAIN}`);
    assert.equal(r.setCookie, undefined);
  }
});

test("no IAP, no session, a foreign or another user's session: nothing is forwarded", async () => {
  const noIap = await resolveUser(request("/x", { iap: null, cookies: { [SESSION_COOKIE]: sessionCookie() } }), deps());
  assert.deepEqual(noIap.ok ? null : noIap.status, 401);
  const none = await resolveUser(request("/x"), deps());
  assert.deepEqual(none.ok ? null : none.body, { error: "sign_in_required", signIn: "/chat/auth/start" });
  const forged = await resolveUser(request("/x", { cookies: { [SESSION_COOKIE]: seal({ v: 1, iapSub: "111", idToken: idToken() }, Buffer.alloc(32, 3)) } }), deps());
  assert.equal(forged.ok, false);
  // Bob's cookie replayed in Alice's IAP session
  const bobs = await resolveUser(request("/x", { cookies: { [SESSION_COOKIE]: sessionCookie({ iapSub: "222", idToken: idToken("222", `bob@${DOMAIN}`) }) } }), deps());
  assert.equal(bobs.ok, false);
  // a session that names Alice but carries Bob's token
  const swapped = await resolveUser(request("/x", { cookies: { [SESSION_COOKIE]: sessionCookie({ idToken: idToken("222", `bob@${DOMAIN}`) }) } }), deps());
  assert.deepEqual(swapped.ok ? null : swapped.status, 403);
});

test("a token close to expiry is renewed with the refresh token and a new cookie", async () => {
  const seen: URLSearchParams[] = [];
  const old = idToken("111", undefined, { exp: NOW + 60 });
  const r = await resolveUser(
    request("/x", { cookies: { [SESSION_COOKIE]: sessionCookie({ idToken: old }) } }),
    deps(tokenEndpoint({ id_token: idToken("111") }, seen)),
  );
  assert.equal(r.ok, true);
  assert.equal(seen[0].get("grant_type"), "refresh_token");
  assert.equal(seen[0].get("refresh_token"), "refresh-1");
  if (r.ok) {
    assert.notEqual(r.idToken, old);
    const renewed = unseal<Session>(readCookie(r.setCookie?.split(";")[0] ?? "", SESSION_COOKIE), signIn.key);
    assert.equal(renewed?.idToken, r.idToken);
  }
  const noRefresh = await resolveUser(request("/x", { cookies: { [SESSION_COOKIE]: sessionCookie({ idToken: old, refreshToken: undefined }) } }), deps());
  assert.deepEqual(noRefresh.ok ? null : noRefresh.status, 401);
});
