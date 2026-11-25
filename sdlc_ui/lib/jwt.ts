// JWT verification: ES256 (IAP assertions) and RS256 on a JWKS, with Node's own crypto. No React: unit-tested
// in tests/identity.test.ts.
// Fail closed: a token is accepted only with the one expected algorithm, a known key id, a valid
// signature, a matching issuer and audience, and a time window that holds (60 s leeway).

import { createPublicKey, type JsonWebKey, verify } from "node:crypto";

export type Jwk = JsonWebKey & { kid?: string };
export type KeySource = (kid: string) => Promise<Jwk | undefined>;
export type Claims = Record<string, unknown>;

export class JwtError extends Error {
  readonly reason: string;

  constructor(reason: string) {
    super(reason);
    this.reason = reason;
    this.name = "JwtError";
  }
}

const LEEWAY_S = 60;

function b64json(part: string): Claims {
  try {
    const value = JSON.parse(Buffer.from(part, "base64url").toString("utf8"));
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("not an object");
    return value as Claims;
  } catch {
    throw new JwtError("malformed");
  }
}

/** The payload of a JWT WITHOUT checking it: only for reading `exp` of a token we hold. */
export function unverifiedClaims(token: string): Claims {
  const parts = token.split(".");
  if (parts.length !== 3) throw new JwtError("malformed");
  return b64json(parts[1]);
}

export async function verifyJwt(
  token: string,
  options: {
    alg: "RS256" | "ES256";
    keys: KeySource;
    issuers: string[];
    audiences: string[];
    now?: number; // seconds
  },
): Promise<Claims> {
  const parts = typeof token === "string" ? token.split(".") : [];
  if (parts.length !== 3 || parts.some((p) => !p)) throw new JwtError("malformed");
  const header = b64json(parts[0]);
  if (header.alg !== options.alg) throw new JwtError("wrong_algorithm");
  if (typeof header.kid !== "string" || !header.kid) throw new JwtError("no_key_id");
  const jwk = await options.keys(header.kid);
  if (!jwk) throw new JwtError("unknown_key");
  let key;
  try {
    key = createPublicKey({ key: jwk, format: "jwk" });
  } catch {
    throw new JwtError("bad_key");
  }
  const data = Buffer.from(`${parts[0]}.${parts[1]}`);
  const signature = Buffer.from(parts[2], "base64url");
  const ok =
    options.alg === "RS256"
      ? verify("sha256", data, key, signature)
      : verify("sha256", data, { key, dsaEncoding: "ieee-p1363" }, signature);
  if (!ok) throw new JwtError("bad_signature");

  const claims = b64json(parts[1]);
  const now = options.now ?? Math.floor(Date.now() / 1000);
  if (typeof claims.exp !== "number" || claims.exp < now - LEEWAY_S) throw new JwtError("expired");
  if (typeof claims.iat === "number" && claims.iat > now + LEEWAY_S) throw new JwtError("not_yet_valid");
  if (typeof claims.nbf === "number" && claims.nbf > now + LEEWAY_S) throw new JwtError("not_yet_valid");
  if (typeof claims.iss !== "string" || !options.issuers.includes(claims.iss)) throw new JwtError("wrong_issuer");
  const aud = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (!aud.some((a) => typeof a === "string" && options.audiences.includes(a))) throw new JwtError("wrong_audience");
  return claims;
}

/**
 * Keys from a JWKS URL, cached for an hour; an unknown key id refetches at most once a minute
 * (keys rotate). A fetch failure gives no key (the token is refused).
 */
export function jwksSource(
  url: string,
  fetchImpl: typeof fetch = fetch,
  clock: () => number = Date.now,
): KeySource {
  let keys = new Map<string, Jwk>();
  let fetchedAt = -Infinity;
  let loading: Promise<void> | undefined;

  const load = () =>
    (loading ??= fetchImpl(url, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error(`JWKS HTTP ${response.status}`);
        const body = (await response.json()) as { keys?: Jwk[] };
        keys = new Map((body.keys ?? []).filter((k) => k.kid).map((k) => [k.kid as string, k]));
        fetchedAt = clock();
      })
      .catch((error: unknown) => {
        console.error("JWKS fetch failed:", error instanceof Error ? error.message : typeof error);
      })
      .finally(() => {
        loading = undefined;
      }));

  return async (kid: string) => {
    const age = clock() - fetchedAt;
    if (age > 3_600_000 || (!keys.has(kid) && age > 60_000)) await load();
    return keys.get(kid);
  };
}
