// sdlc_ui's own credentials on Cloud Run, from the metadata server: an access token to call Agent Runtime and ID
// tokens to prove itself to user_agent_mcp (DEC-0010). They identify sdlc_ui as the caller, never the user, and
// are cached until shortly before they expire. No React: unit-tested in tests/backends.test.ts.

import { unverifiedClaims } from "./jwt.ts";

const METADATA = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default";
const MARGIN_MS = 120_000;

type Cached = { token: string; expiresAt: number };

export interface Tokens {
  accessToken(): Promise<string>;
  idToken(audience: string): Promise<string>;
}

export class ServiceTokens implements Tokens {
  private access?: Cached;
  private readonly ids = new Map<string, Cached>();
  private readonly fetchImpl: typeof fetch;
  private readonly base: string;
  private readonly clock: () => number;

  constructor(fetchImpl: typeof fetch = fetch, base: string = METADATA, clock: () => number = Date.now) {
    this.fetchImpl = fetchImpl;
    this.base = base;
    this.clock = clock;
  }

  private async get(path: string): Promise<Response> {
    const response = await this.fetchImpl(`${this.base}/${path}`, {
      headers: { "Metadata-Flavor": "Google" },
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`metadata server HTTP ${response.status}`);
    return response;
  }

  async accessToken(): Promise<string> {
    if (this.access && this.access.expiresAt - MARGIN_MS > this.clock()) return this.access.token;
    const body = (await (await this.get("token")).json()) as { access_token: string; expires_in: number };
    this.access = { token: body.access_token, expiresAt: this.clock() + body.expires_in * 1000 };
    return body.access_token;
  }

  async idToken(audience: string): Promise<string> {
    const hit = this.ids.get(audience);
    if (hit && hit.expiresAt - MARGIN_MS > this.clock()) return hit.token;
    const path = `identity?audience=${encodeURIComponent(audience)}&format=full`;
    const token = (await (await this.get(path)).text()).trim();
    const exp = unverifiedClaims(token).exp;
    this.ids.set(audience, { token, expiresAt: typeof exp === "number" ? exp * 1000 : this.clock() });
    return token;
  }
}
