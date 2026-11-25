import assert from "node:assert/strict";
import { generateKeyPairSync, sign } from "node:crypto";
import { test } from "node:test";

import { authSettings, IAP_HEADER, IAP_ISSUER, userOf } from "../lib/identity.ts";

const AUDIENCE = "/projects/123/locations/europe-west3/services/sdlc-ui";
const { privateKey, publicKey } = generateKeyPairSync("ec", { namedCurve: "P-256" });
const keys = async (kid: string) => (kid === "k1" ? { ...publicKey.export({ format: "jwk" }), kid: "k1" } : undefined);
const NOW = 1_800_000_000;

function assertion(claims: Record<string, unknown>, kid = "k1"): string {
  const b64 = (v: unknown) => Buffer.from(JSON.stringify(v)).toString("base64url");
  const head = `${b64({ alg: "ES256", kid })}.${b64({ iss: IAP_ISSUER, aud: AUDIENCE, exp: NOW + 600, iat: NOW, ...claims })}`;
  return `${head}.${sign("sha256", Buffer.from(head), { key: privateKey, dsaEncoding: "ieee-p1363" }).toString("base64url")}`;
}

const iap = { mode: "iap", audience: AUDIENCE } as const;
const headers = (value: string) => new Headers({ [IAP_HEADER]: value });

test("the user comes from a verified IAP assertion, without IAP's prefix", async () => {
  const user = await userOf(headers(assertion({ sub: "accounts.google.com:1001", email: "accounts.google.com:Ada@Example.test" })), iap, keys, NOW);
  assert.deepEqual(user, { id: "1001", email: "ada@example.test" });
});

test("anything else is refused", async () => {
  const good = { sub: "accounts.google.com:1001", email: "ada@example.test" };
  for (const bad of [
    "",
    assertion(good, "unknown"),
    assertion({ ...good, aud: "/projects/123/locations/europe-west3/services/other" }),
    assertion({ ...good, iss: "https://evil.test" }),
    assertion({ ...good, exp: NOW - 3600 }),
    assertion({ sub: "accounts.google.com:1001" }),
    assertion(good).slice(0, -4) + "AAAA",
  ]) {
    await assert.rejects(userOf(headers(bad), iap, keys, NOW));
  }
  // IAP's unsigned headers mean nothing
  await assert.rejects(userOf(new Headers({ "x-goog-authenticated-user-email": "accounts.google.com:ada@example.test" }), iap, keys, NOW));
});

test("settings fail closed; a fixed local user only in the local environment", () => {
  assert.throws(() => authSettings({}));
  assert.throws(() => authSettings({ SDLC_AUTH: "local", SDLC_ENV: "dev", SDLC_LOCAL_USER_ID: "1", SDLC_LOCAL_USER_EMAIL: "a@x.test" }));
  assert.throws(() => authSettings({ SDLC_AUTH: "local", SDLC_ENV: "local" }));
  assert.deepEqual(authSettings({ SDLC_AUTH: "local", SDLC_ENV: "local", SDLC_LOCAL_USER_ID: "1", SDLC_LOCAL_USER_EMAIL: "A@x.test" }), {
    mode: "local",
    user: { id: "1", email: "a@x.test" },
  });
  assert.deepEqual(authSettings({ SDLC_IAP_AUDIENCE: AUDIENCE }), iap);
});
