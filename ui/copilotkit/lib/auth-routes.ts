// The sign-in routes of the native stack (CH-0016): /chat/auth/start, /callback, /sign_out.
// Thin Next.js route files call these. No React: unit-tested in tests/session.test.ts.

import { IAP_HEADER, sameUser, verifyIap, verifyIdToken } from "./identity.ts";
import { type NativeDeps, nativeDeps } from "./native.ts";
import {
  authorizationUrl,
  clearCookie,
  exchangeCode,
  type Flow,
  FLOW_COOKIE,
  FLOW_MAX_AGE_S,
  newFlow,
  readCookie,
  SESSION_COOKIE,
  SESSION_MAX_AGE_S,
  type Session,
  SIGN_IN_PATH,
  safeReturnTo,
  seal,
  setCookie,
  unseal,
} from "./session.ts";

// Google's answers to prompt=none that a consent prompt can fix
const NEEDS_PROMPT = new Set(["interaction_required", "consent_required", "login_required", "account_selection_required"]);
export const IAP_SIGN_OUT = "/?gcp-iap-mode=CLEAR_LOGIN_COOKIE";

function redirect(location: string, cookies: string[] = []): Response {
  const headers = new Headers({ location, "cache-control": "no-store" });
  for (const c of cookies) headers.append("set-cookie", c);
  return new Response(null, { status: 302, headers });
}

function denied(status: number, message: string, cookies: string[] = []): Response {
  const headers = new Headers({ "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" });
  for (const c of cookies) headers.append("set-cookie", c);
  return new Response(message, { status, headers });
}

function startUrl(d: NativeDeps, returnTo: string, consent: boolean): string {
  const query = new URLSearchParams({ returnTo, ...(consent ? { consent: "1" } : {}) });
  return `${d.signIn.publicUrl}${SIGN_IN_PATH}?${query}`;
}

/** GET /chat/auth/start: begin the code flow for the IAP user. */
export async function startSignIn(request: Request, d: NativeDeps = nativeDeps()): Promise<Response> {
  let iap;
  try {
    iap = await verifyIap(request.headers.get(IAP_HEADER), d.identity, d.keys.iap, d.now?.());
  } catch {
    return denied(401, "Not signed in.");
  }
  const params = new URL(request.url).searchParams;
  const flow = newFlow(iap.sub, safeReturnTo(params.get("returnTo")), params.get("consent") === "1");
  const cookie = setCookie(FLOW_COOKIE, seal(flow, d.signIn.key), FLOW_MAX_AGE_S);
  return redirect(authorizationUrl(flow, d.signIn, iap.email), [cookie]);
}

/** GET /chat/auth/callback: finish the code flow and start the session. */
export async function finishSignIn(request: Request, d: NativeDeps = nativeDeps()): Promise<Response> {
  const now = d.now?.();
  let iap;
  try {
    iap = await verifyIap(request.headers.get(IAP_HEADER), d.identity, d.keys.iap, now);
  } catch {
    return denied(401, "Not signed in.");
  }
  const flow = unseal<Flow>(readCookie(request.headers.get("cookie"), FLOW_COOKIE), d.signIn.key);
  const params = new URL(request.url).searchParams;
  const clearFlow = clearCookie(FLOW_COOKIE);
  if (!flow || flow.v !== 1 || flow.iapSub !== iap.sub || params.get("state") !== flow.state) {
    return denied(400, "The sign-in expired or did not start here. Reload the page.", [clearFlow]);
  }
  const error = params.get("error");
  if (error) {
    if (NEEDS_PROMPT.has(error) && !flow.consent) return redirect(startUrl(d, flow.returnTo, true), [clearFlow]);
    return denied(403, "Google sign-in was not completed.", [clearFlow]);
  }
  const code = params.get("code");
  if (!code) return denied(400, "No authorization code.", [clearFlow]);
  let tokens;
  try {
    tokens = await exchangeCode(code, flow, d.signIn, d.fetchImpl);
  } catch (e) {
    console.error("sign-in code exchange failed:", e instanceof Error ? e.message : typeof e);
    return denied(502, "Google sign-in failed. Please try again.", [clearFlow]);
  }
  let user;
  try {
    user = await verifyIdToken(tokens.idToken, d.identity, d.keys.google, now);
  } catch {
    return denied(403, "This Google account may not use the assistant.", [clearFlow]);
  }
  if (!sameUser(iap, user)) {
    console.warn("sign-in refused: the Google account is not the IAP user");
    return denied(403, "Sign in with the same account you used to open this page.", [clearFlow]);
  }
  if (!tokens.refreshToken && !flow.consent) {
    // no way to renew the 1-hour token silently: ask once with consent, which returns one
    return redirect(startUrl(d, flow.returnTo, true), [clearFlow]);
  }
  const session: Session = { v: 1, iapSub: iap.sub, idToken: tokens.idToken, refreshToken: tokens.refreshToken };
  return redirect(`${d.signIn.publicUrl}${flow.returnTo}`, [
    clearFlow,
    setCookie(SESSION_COOKIE, seal(session, d.signIn.key), SESSION_MAX_AGE_S),
  ]);
}

/** GET /chat/auth/sign_out (and /oauth2/sign_out): drop the session, then IAP's login cookie. */
export function signOut(): Response {
  return redirect(IAP_SIGN_OUT, [clearCookie(SESSION_COOKIE), clearCookie(FLOW_COOKIE)]);
}
