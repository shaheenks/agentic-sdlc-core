// The native stack's request check (CH-0016): every route handler that acts for a user calls
// `resolveUser` first. No React: unit-tested in tests/session.test.ts.
//
// 1. IAP's assertion decides who is here (no valid assertion: 401, nothing else is looked at).
// 2. The session cookie must be ours and bound to that IAP user; otherwise sign in again.
// 3. An ID token close to expiry is renewed with the refresh token (a new cookie is returned).
// 4. The ID token must pass the agent's checks and name the IAP user.
// Only then does the handler get the token to forward. Errors carry no token and no claims.

import {
  defaultKeys,
  type GoogleUser,
  IAP_HEADER,
  type IdentityKeys,
  type IdentitySettings,
  identitySettings,
  sameUser,
  verifyIap,
  verifyIdToken,
} from "./identity.ts";
import {
  needsRenewal,
  readCookie,
  renewIdToken,
  SESSION_COOKIE,
  SESSION_MAX_AGE_S,
  type Session,
  SIGN_IN_PATH,
  type SignInSettings,
  seal,
  setCookie,
  signInSettings,
  unseal,
} from "./session.ts";

export type NativeDeps = {
  identity: IdentitySettings;
  signIn: SignInSettings;
  keys: IdentityKeys;
  fetchImpl: typeof fetch;
  now?: () => number; // seconds
};

export type Resolved =
  | { ok: true; user: GoogleUser; idToken: string; setCookie?: string }
  | { ok: false; status: 401 | 403; body: { error: string; signIn?: string } };

/** The native stack is on when the UI talks to Agent Runtime (SDLC_AGENT_BACKEND). */
export function nativeEnabled(env: Record<string, string | undefined> = process.env): boolean {
  return env.SDLC_AGENT_BACKEND === "agent-runtime";
}

let deps: NativeDeps | undefined;
export function nativeDeps(): NativeDeps {
  deps ??= { identity: identitySettings(), signIn: signInSettings(), keys: defaultKeys(), fetchImpl: fetch };
  return deps;
}

const signInAgain: Resolved = {
  ok: false,
  status: 401,
  body: { error: "sign_in_required", signIn: SIGN_IN_PATH },
};

export async function resolveUser(request: Request, d: NativeDeps = nativeDeps()): Promise<Resolved> {
  const now = d.now?.();
  let iap;
  try {
    iap = await verifyIap(request.headers.get(IAP_HEADER), d.identity, d.keys.iap, now);
  } catch {
    return { ok: false, status: 401, body: { error: "not_signed_in" } }; // IAP should have stopped it
  }
  const session = unseal<Session>(readCookie(request.headers.get("cookie"), SESSION_COOKIE), d.signIn.key);
  if (!session || session.v !== 1 || session.iapSub !== iap.sub) return signInAgain;

  let { idToken } = session;
  let cookie: string | undefined;
  if (needsRenewal(idToken, now)) {
    if (!session.refreshToken) return signInAgain;
    try {
      idToken = await renewIdToken(session.refreshToken, d.signIn, d.fetchImpl);
    } catch (error) {
      console.error("ID token renewal failed:", error instanceof Error ? error.message : typeof error);
      return signInAgain;
    }
    cookie = setCookie(SESSION_COOKIE, seal({ ...session, idToken }, d.signIn.key), SESSION_MAX_AGE_S);
  }
  let user: GoogleUser;
  try {
    user = await verifyIdToken(idToken, d.identity, d.keys.google, now);
  } catch {
    return signInAgain;
  }
  if (!sameUser(iap, user)) {
    console.warn("session refused: its Google account is not the IAP user");
    return { ok: false, status: 403, body: { error: "identity_mismatch", signIn: SIGN_IN_PATH } };
  }
  return { ok: true, user, idToken, ...(cookie ? { setCookie: cookie } : {}) };
}

export function refusal(resolved: Extract<Resolved, { ok: false }>): Response {
  return Response.json(resolved.body, { status: resolved.status, headers: { "cache-control": "no-store" } });
}

/** Adds a renewed session cookie to a response, if there is one. */
export function withSession(response: Response, resolved: Extract<Resolved, { ok: true }>): Response {
  if (!resolved.setCookie) return response;
  const headers = new Headers(response.headers);
  headers.append("set-cookie", resolved.setCookie);
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}
