// Who the user is (DEC-0010). No React: unit-tested in tests/identity.test.ts.
//
// - In Google Cloud, IAP signs every request it lets through with `X-Goog-IAP-JWT-Assertion` (ES256, issuer
//   https://cloud.google.com/iap, audience = this service). The user's account ID and email come from that
//   verified assertion only, never from IAP's unsigned x-goog-authenticated-user-* headers, and the assertion
//   itself is never forwarded.
// - In the local environment only, `SDLC_AUTH=local` names a fixed user (SDLC_LOCAL_USER_ID and _EMAIL).
// Anything missing or unverifiable is refused (fail closed).

import { type KeySource, jwksSource, verifyJwt } from "./jwt.ts";

export const IAP_ISSUER = "https://cloud.google.com/iap";
export const IAP_KEYS_URL = "https://www.gstatic.com/iap/verify/public_key-jwk";
export const IAP_HEADER = "x-goog-iap-jwt-assertion";
const IAP_PREFIX = /^accounts\.google\.com:/;

export type User = { id: string; email: string };

export type AuthSettings =
  | { mode: "iap"; audience: string }
  | { mode: "local"; user: User };

const USER_ID = /^[A-Za-z0-9_-]{1,128}$/;
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/** Settings from the environment; anything missing or not allowed throws (fail closed). */
export function authSettings(env: Record<string, string | undefined> = process.env): AuthSettings {
  const mode = env.SDLC_AUTH ?? "iap";
  if (mode === "local") {
    if ((env.SDLC_ENV ?? "") !== "local") throw new Error("SDLC_AUTH=local is allowed only with SDLC_ENV=local");
    const user = { id: env.SDLC_LOCAL_USER_ID ?? "", email: (env.SDLC_LOCAL_USER_EMAIL ?? "").toLowerCase() };
    if (!USER_ID.test(user.id) || !EMAIL.test(user.email)) {
      throw new Error("SDLC_LOCAL_USER_ID and SDLC_LOCAL_USER_EMAIL must name the local user");
    }
    return { mode, user };
  }
  if (mode !== "iap") throw new Error("SDLC_AUTH must be iap or local");
  const audience = env.SDLC_IAP_AUDIENCE ?? "";
  if (!audience) throw new Error("SDLC_IAP_AUDIENCE must be set (/projects/<number>/locations/<region>/services/<name>)");
  return { mode, audience };
}

let iapKeys: KeySource | undefined;

/** The signed-in user of one request, or an Error. */
export async function userOf(
  headers: Headers,
  settings: AuthSettings,
  keys: KeySource = (iapKeys ??= jwksSource(IAP_KEYS_URL)),
  now?: number,
): Promise<User> {
  if (settings.mode === "local") return settings.user;
  const claims = await verifyJwt(headers.get(IAP_HEADER) ?? "", {
    alg: "ES256",
    keys,
    issuers: [IAP_ISSUER],
    audiences: [settings.audience],
    now,
  });
  const id = String(claims.sub ?? "").replace(IAP_PREFIX, "");
  const email = String(claims.email ?? "").replace(IAP_PREFIX, "").toLowerCase();
  if (!USER_ID.test(id) || !EMAIL.test(email)) throw new Error("IAP assertion without a well-formed user");
  return { id, email };
}
