// Who the user is on the native stack (CH-0016): the IAP assertion and the user's Google ID token
// are verified strictly, and must name the same account.

import assert from "node:assert/strict";
import { test } from "node:test";

import { identitySettings, sameUser, verifyIap, verifyIdToken } from "../lib/identity.ts";
import { verifyJwt } from "../lib/jwt.ts";
import { CLIENT, DOMAIN, iapAssertion, identity, idToken, jwt, keys, NOW, otherRsa } from "./fake-google.ts";

test("an IAP assertion names the user without the accounts.google.com prefix", async () => {
  const user = await verifyIap(iapAssertion("111"), identity, keys.iap, NOW);
  assert.deepEqual(user, { sub: "111", email: `alice@${DOMAIN}` });
});

test("an IAP assertion for another service, expired or missing is refused", async () => {
  await assert.rejects(verifyIap(iapAssertion("1", undefined, { aud: "/projects/1/other" }), identity, keys.iap, NOW), /wrong_audience/);
  await assert.rejects(verifyIap(iapAssertion("1", undefined, { exp: NOW - 120 }), identity, keys.iap, NOW), /expired/);
  await assert.rejects(verifyIap(iapAssertion("1", undefined, { iss: "https://evil.test" }), identity, keys.iap, NOW), /wrong_issuer/);
  await assert.rejects(verifyIap(null, identity, keys.iap, NOW), /malformed/);
});

test("a Google ID token passes the agent's checks", async () => {
  const user = await verifyIdToken(idToken("111"), identity, keys.google, NOW);
  assert.deepEqual(user, { sub: "111", email: `alice@${DOMAIN}`, name: "Alice", domain: DOMAIN });
});

for (const [why, extra, reason] of [
  ["another client's token", { aud: "someone-else" }, /wrong_audience/],
  ["an unverified email", { email_verified: false }, /not verified/],
  ["another domain", { hd: "elsewhere.test" }, /domain/],
  ["a consumer account (no hd)", { hd: undefined }, /domain/],
  ["an expired token", { exp: NOW - 120 }, /expired/],
  ["a token without https issuer", { iss: "accounts.google.com" }, /wrong_issuer/],
] as const) {
  test(`a Google ID token is refused: ${why}`, async () => {
    await assert.rejects(verifyIdToken(idToken("111", undefined, extra), identity, keys.google, NOW), reason);
  });
}

test("a forged signature, another algorithm or an unknown key is refused", async () => {
  const forged = jwt("RS256", otherRsa.privateKey, "google-1", { iss: "https://accounts.google.com", aud: CLIENT, exp: NOW + 60 });
  await assert.rejects(verifyIdToken(forged, identity, keys.google, NOW), /bad_signature/);
  const [, payload] = idToken().split(".");
  const none = `${Buffer.from(JSON.stringify({ alg: "none", kid: "google-1" })).toString("base64url")}.${payload}.`;
  await assert.rejects(verifyIdToken(none, identity, keys.google, NOW), /malformed|wrong_algorithm/);
  const unknown = jwt("RS256", otherRsa.privateKey, "google-9", { exp: NOW + 60 });
  await assert.rejects(verifyJwt(unknown, { alg: "RS256", keys: keys.google, issuers: [], audiences: [], now: NOW }), /unknown_key/);
  // an IAP key (ES256) never verifies an ID token (RS256), and the other way round
  await assert.rejects(verifyIdToken(iapAssertion(), identity, keys.google, NOW), /wrong_algorithm/);
});

test("the ID token must be the IAP user's", async () => {
  const iap = await verifyIap(iapAssertion("111"), identity, keys.iap, NOW);
  assert.equal(sameUser(iap, await verifyIdToken(idToken("111"), identity, keys.google, NOW)), true);
  const bob = await verifyIdToken(idToken("222", `bob@${DOMAIN}`), identity, keys.google, NOW);
  assert.equal(sameUser(iap, bob), false);
});

test("missing settings stop the native stack (fail closed)", () => {
  assert.throws(() => identitySettings({ SDLC_OAUTH_CLIENT_IDS: CLIENT, SDLC_ALLOWED_DOMAINS: DOMAIN }), /must be set/);
  const ok = identitySettings({ SDLC_IAP_AUDIENCE: "/p", SDLC_OAUTH_CLIENT_IDS: ` ${CLIENT} ,`, SDLC_ALLOWED_DOMAINS: "Example.Test" });
  assert.deepEqual(ok, { iapAudience: "/p", clientIds: [CLIENT], domains: ["example.test"] });
});
