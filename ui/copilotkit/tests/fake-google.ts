// Test issuers (CH-0016): an IAP (ES256) and a Google OAuth issuer (RS256) with their own keys.
// Placeholders only: never a real client, domain or audience.

import { createPrivateKey, generateKeyPairSync, type KeyObject, sign } from "node:crypto";

import type { IdentityKeys, IdentitySettings } from "../lib/identity.ts";
import type { Jwk } from "../lib/jwt.ts";
import type { NativeDeps } from "../lib/native.ts";
import type { SignInSettings } from "../lib/session.ts";

export const CLIENT = "web-client.apps.googleusercontent.com";
export const DOMAIN = "example.test";
export const IAP_AUD = "/projects/1/locations/r/services/sdlc-ui-native";
export const NOW = 1_800_000_000;

type Pair = { privateKey: KeyObject; jwk: Jwk };

function pair(kind: "rsa" | "ec", kid: string): Pair {
  const keys =
    kind === "rsa"
      ? generateKeyPairSync("rsa", { modulusLength: 2048 })
      : generateKeyPairSync("ec", { namedCurve: "P-256" });
  return { privateKey: keys.privateKey, jwk: { ...(keys.publicKey.export({ format: "jwk" }) as Jwk), kid } };
}

const iapKey = pair("ec", "iap-1");
const googleKey = pair("rsa", "google-1");
export const otherRsa = pair("rsa", "google-1"); // same kid, other key: a forged signature

const b64 = (value: unknown) => Buffer.from(JSON.stringify(value)).toString("base64url");

export function jwt(alg: "RS256" | "ES256", key: KeyObject, kid: string, claims: Record<string, unknown>): string {
  const head = `${b64({ alg, kid, typ: "JWT" })}.${b64(claims)}`;
  const signature =
    alg === "RS256"
      ? sign("sha256", Buffer.from(head), key)
      : sign("sha256", Buffer.from(head), { key, dsaEncoding: "ieee-p1363" });
  return `${head}.${signature.toString("base64url")}`;
}

export function iapAssertion(sub = "111", email = `alice@${DOMAIN}`, extra: Record<string, unknown> = {}): string {
  return jwt("ES256", iapKey.privateKey, "iap-1", {
    iss: "https://cloud.google.com/iap",
    aud: IAP_AUD,
    sub: `accounts.google.com:${sub}`,
    email: `accounts.google.com:${email}`,
    iat: NOW - 10,
    exp: NOW + 600,
    ...extra,
  });
}

export function idToken(sub = "111", email = `alice@${DOMAIN}`, extra: Record<string, unknown> = {}): string {
  return jwt("RS256", googleKey.privateKey, "google-1", {
    iss: "https://accounts.google.com",
    aud: CLIENT,
    sub,
    email,
    email_verified: true,
    hd: DOMAIN,
    name: "Alice",
    iat: NOW - 10,
    exp: NOW + 3600,
    ...extra,
  });
}

export const keys: IdentityKeys = {
  iap: async (kid) => (kid === "iap-1" ? iapKey.jwk : undefined),
  google: async (kid) => (kid === "google-1" ? googleKey.jwk : undefined),
};

export const identity: IdentitySettings = { iapAudience: IAP_AUD, clientIds: [CLIENT], domains: [DOMAIN] };

export const signIn: SignInSettings = {
  webClientId: CLIENT,
  webClientSecret: "test-secret",
  publicUrl: "https://ui.example.test",
  key: Buffer.alloc(32, 7),
};

export function deps(fetchImpl: typeof fetch = fetch): NativeDeps {
  return { identity, signIn, keys, fetchImpl, now: () => NOW };
}

export { createPrivateKey };
