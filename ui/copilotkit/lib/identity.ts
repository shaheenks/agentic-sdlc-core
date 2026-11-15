// Who the user is on the native stack (CH-0016). No React: unit-tested in tests/identity.test.ts.
//
// - IAP signs every request it lets through with `X-Goog-IAP-JWT-Assertion` (ES256, issuer
//   https://cloud.google.com/iap, audience = this service). That decides WHO is here; it is never
//   forwarded (its audience is IAP, not our OAuth client).
// - The user's own Google ID token (from the server-side sign-in, lib/session.ts) is checked with
//   the agent's rules: one of our OAuth clients, verified email, an allowed Cloud Identity domain.
// - Both must name the same Google account (`sub`), or the request is refused.

import { type Claims, type KeySource, jwksSource, verifyJwt } from "./jwt.ts";

export const IAP_ISSUER = "https://cloud.google.com/iap";
export const IAP_KEYS_URL = "https://www.gstatic.com/iap/verify/public_key-jwk";
export const IAP_HEADER = "x-goog-iap-jwt-assertion";
export const GOOGLE_ISSUER = "https://accounts.google.com"; // as sdlc_auth.google
export const GOOGLE_KEYS_URL = "https://www.googleapis.com/oauth2/v3/certs";

export type IapUser = { sub: string; email: string };
export type GoogleUser = { sub: string; email: string; name: string; domain: string };

export type IdentitySettings = {
  iapAudience: string;
  clientIds: string[]; // our OAuth clients: the ID token audience
  domains: string[]; // allowed Cloud Identity domains (lower case)
};

export type IdentityKeys = { iap: KeySource; google: KeySource };

export function defaultKeys(fetchImpl: typeof fetch = fetch): IdentityKeys {
  return { iap: jwksSource(IAP_KEYS_URL, fetchImpl), google: jwksSource(GOOGLE_KEYS_URL, fetchImpl) };
}

const list = (value: string | undefined): string[] =>
  (value ?? "")
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);

/** Identity settings from the environment; anything missing throws (fail closed). */
export function identitySettings(env: Record<string, string | undefined> = process.env): IdentitySettings {
  const settings = {
    iapAudience: env.SDLC_IAP_AUDIENCE ?? "",
    clientIds: list(env.SDLC_OAUTH_CLIENT_IDS),
    domains: list(env.SDLC_ALLOWED_DOMAINS).map((d) => d.toLowerCase()),
  };
  if (!settings.iapAudience || !settings.clientIds.length || !settings.domains.length) {
    throw new Error("SDLC_IAP_AUDIENCE, SDLC_OAUTH_CLIENT_IDS and SDLC_ALLOWED_DOMAINS must be set");
  }
  return settings;
}

const text = (claims: Claims, name: string): string => {
  const value = claims[name];
  return typeof value === "string" ? value : "";
};

export async function verifyIap(
  assertion: string | null,
  settings: IdentitySettings,
  keys: KeySource,
  now?: number,
): Promise<IapUser> {
  const claims = await verifyJwt(assertion ?? "", {
    alg: "ES256",
    keys,
    issuers: [IAP_ISSUER],
    audiences: [settings.iapAudience],
    now,
  });
  // IAP's sub is "accounts.google.com:<id>": the same id as the ID token's sub
  const sub = text(claims, "sub").replace(/^accounts\.google\.com:/, "");
  const email = text(claims, "email").replace(/^accounts\.google\.com:/, "").toLowerCase();
  if (!sub || !email) throw new Error("IAP assertion without a user");
  return { sub, email };
}

export async function verifyIdToken(
  token: string,
  settings: IdentitySettings,
  keys: KeySource,
  now?: number,
): Promise<GoogleUser> {
  const claims = await verifyJwt(token, {
    alg: "RS256",
    keys,
    issuers: [GOOGLE_ISSUER],
    audiences: settings.clientIds,
    now,
  });
  const sub = text(claims, "sub");
  const email = text(claims, "email").toLowerCase();
  const domain = text(claims, "hd").toLowerCase();
  if (!sub || !email) throw new Error("ID token without sub or email");
  if (claims.email_verified !== true) throw new Error("email not verified");
  if (!settings.domains.includes(domain)) throw new Error("domain not allowed");
  return { sub, email, name: text(claims, "name"), domain };
}

/** The ID token belongs to the user IAP let in. */
export function sameUser(iap: IapUser, user: GoogleUser): boolean {
  return iap.sub === user.sub && iap.email === user.email;
}
