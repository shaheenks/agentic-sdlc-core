// The UI service account's own credentials on Cloud Run (CH-0016), from the metadata server:
// an access token to query Agent Runtime, and ID tokens for Cloud Run IAM (sdlc-mcp-native).
// They identify the UI as the caller, never the user: the user is always the forwarded ID token.
// Cached until shortly before they expire. No React: unit-tested in tests/agent-runtime.test.ts.

import { unverifiedClaims } from "./jwt.ts";

const METADATA = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default";
const MARGIN_MS = 120_000;

type Cached = { token: string; expiresAt: number };

export class ServiceTokens {
  private access?: Cached;
  private readonly ids = new Map<string, Cached>();

  private readonly fetchImpl: typeof fetch;
  private readonly base: string;
  private readonly clock: () => number;

  constructor(
    fetchImpl: typeof fetch = fetch,
    base: string = process.env.SDLC_METADATA_URL || METADATA,
    clock: () => number = Date.now,
  ) {
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
    const token = (await (await this.get(`identity?audience=${encodeURIComponent(audience)}&format=full`)).text()).trim();
    const exp = unverifiedClaims(token).exp;
    this.ids.set(audience, { token, expiresAt: typeof exp === "number" ? exp * 1000 : this.clock() });
    return token;
  }
}
