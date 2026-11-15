// Server-side Google sign-in for the native stack (CH-0016). No React: unit-tested in
// tests/session.test.ts.
//
// After IAP has let the user in, the UI server gets the user's OWN Google ID token for our Web
// OAuth client with the authorization code flow (PKCE + state, `prompt=none` and the IAP user as
// `login_hint`, so it is silent). Offline access is asked for so the ID token can be renewed
// without a redirect; if Google returns no refresh token, the flow runs once more with
// `prompt=consent` (one click per session). Tokens live only in one cookie, sealed with
// AES-256-GCM (key from Secret Manager), httpOnly, Secure, SameSite=Lax, and bound to the IAP
// user. They never reach browser JavaScript and are never logged.

import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";

import { unverifiedClaims } from "./jwt.ts";

export const SESSION_COOKIE = "__Host-sdlc_session";
export const FLOW_COOKIE = "__Host-sdlc_signin";
export const SESSION_MAX_AGE_S = 8 * 3600;
export const FLOW_MAX_AGE_S = 600;
export const SIGN_IN_PATH = "/chat/auth/start";
export const CALLBACK_PATH = "/chat/auth/callback";
export const AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth";
export const TOKEN_URL = "https://oauth2.googleapis.com/token";
const RENEW_BEFORE_S = 300;

export type Session = { v: 1; iapSub: string; idToken: string; refreshToken?: string };
export type Flow = { v: 1; state: string; verifier: string; returnTo: string; consent: boolean; iapSub: string };

export type SignInSettings = {
  webClientId: string;
  webClientSecret: string;
  publicUrl: string; // https://<ui host>, configuration (never derived from request headers)
  key: Buffer; // 32 bytes
};

export function signInSettings(env: Record<string, string | undefined> = process.env): SignInSettings {
  const key = Buffer.from(env.SDLC_SESSION_KEY ?? "", "base64url");
  const settings = {
    webClientId: env.SDLC_GOOGLE_WEB_CLIENT_ID ?? "",
    webClientSecret: env.SDLC_GOOGLE_WEB_CLIENT_SECRET ?? "",
    publicUrl: (env.SDLC_PUBLIC_URL ?? "").replace(/\/+$/, ""),
    key,
  };
  if (!settings.webClientId || !settings.webClientSecret || !settings.publicUrl.startsWith("https://") || key.length !== 32) {
    throw new Error(
      "SDLC_GOOGLE_WEB_CLIENT_ID, SDLC_GOOGLE_WEB_CLIENT_SECRET, SDLC_PUBLIC_URL (https) and SDLC_SESSION_KEY (32 bytes, base64url) must be set",
    );
  }
  return settings;
}

// --- sealing --------------------------------------------------------------------------------

export function seal(value: unknown, key: Buffer): string {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  const body = Buffer.concat([cipher.update(JSON.stringify(value), "utf8"), cipher.final()]);
  return Buffer.concat([iv, body, cipher.getAuthTag()]).toString("base64url");
}

/** The sealed value, or null if it was changed, sealed with another key or is not ours. */
export function unseal<T>(sealed: string | undefined, key: Buffer): T | null {
  if (!sealed) return null;
  try {
    const raw = Buffer.from(sealed, "base64url");
    if (raw.length < 12 + 16 + 1) return null;
    const decipher = createDecipheriv("aes-256-gcm", key, raw.subarray(0, 12));
    decipher.setAuthTag(raw.subarray(raw.length - 16));
    const plain = Buffer.concat([decipher.update(raw.subarray(12, raw.length - 16)), decipher.final()]);
    return JSON.parse(plain.toString("utf8")) as T;
  } catch {
    return null;
  }
}

// --- cookies --------------------------------------------------------------------------------

export function readCookie(header: string | null, name: string): string | undefined {
  for (const part of (header ?? "").split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k === name) return v.join("=");
  }
  return undefined;
}

/** `__Host-` cookies: Secure, Path=/, no Domain; httpOnly and SameSite=Lax (the OAuth redirect). */
export function setCookie(name: string, value: string, maxAge: number): string {
  return `${name}=${value}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=${maxAge}`;
}

export function clearCookie(name: string): string {
  return setCookie(name, "", 0);
}

// --- the OAuth flow -------------------------------------------------------------------------

/** A same-site path to return to after sign-in; anything else returns to the chat. */
export function safeReturnTo(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return "/chat/";
  return value;
}

export function newFlow(iapSub: string, returnTo: string, consent: boolean): Flow {
  return {
    v: 1,
    state: randomBytes(24).toString("base64url"),
    verifier: randomBytes(48).toString("base64url"),
    returnTo: safeReturnTo(returnTo),
    consent,
    iapSub,
  };
}

export function authorizationUrl(flow: Flow, settings: SignInSettings, loginHint: string): string {
  const challenge = createHash("sha256").update(flow.verifier).digest("base64url");
  const query = new URLSearchParams({
    client_id: settings.webClientId,
    redirect_uri: settings.publicUrl + CALLBACK_PATH,
    response_type: "code",
    scope: "openid email profile",
    access_type: "offline",
    state: flow.state,
    code_challenge: challenge,
    code_challenge_method: "S256",
    login_hint: loginHint,
    prompt: flow.consent ? "consent" : "none",
  });
  return `${AUTH_URL}?${query}`;
}

type TokenResponse = { id_token?: string; refresh_token?: string };

async function tokenRequest(body: Record<string, string>, fetchImpl: typeof fetch): Promise<TokenResponse> {
  const response = await fetchImpl(TOKEN_URL, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(body),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`token endpoint HTTP ${response.status}`); // never the body
  return (await response.json()) as TokenResponse;
}

export async function exchangeCode(
  code: string,
  flow: Flow,
  settings: SignInSettings,
  fetchImpl: typeof fetch = fetch,
): Promise<{ idToken: string; refreshToken?: string }> {
  const tokens = await tokenRequest(
    {
      grant_type: "authorization_code",
      code,
      code_verifier: flow.verifier,
      redirect_uri: settings.publicUrl + CALLBACK_PATH,
      client_id: settings.webClientId,
      client_secret: settings.webClientSecret,
    },
    fetchImpl,
  );
  if (!tokens.id_token) throw new Error("no ID token from the token endpoint");
  return { idToken: tokens.id_token, refreshToken: tokens.refresh_token };
}

export async function renewIdToken(
  refreshToken: string,
  settings: SignInSettings,
  fetchImpl: typeof fetch = fetch,
): Promise<string> {
  const tokens = await tokenRequest(
    {
      grant_type: "refresh_token",
      refresh_token: refreshToken,
      client_id: settings.webClientId,
      client_secret: settings.webClientSecret,
    },
    fetchImpl,
  );
  if (!tokens.id_token) throw new Error("no ID token on renewal");
  return tokens.id_token;
}

/** Seconds until the token expires (negative: expired); a token we cannot read counts as expired. */
export function secondsLeft(idToken: string, now: number = Math.floor(Date.now() / 1000)): number {
  try {
    const exp = unverifiedClaims(idToken).exp;
    return typeof exp === "number" ? exp - now : -1;
  } catch {
    return -1;
  }
}

export const needsRenewal = (idToken: string, now?: number): boolean => secondsLeft(idToken, now) < RENEW_BEFORE_S;
