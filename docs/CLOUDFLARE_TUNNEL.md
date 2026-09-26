# Public endpoints: Cloudflare Tunnel

> **Scope: development environment only.** Dev is reachable both on `localhost` and through
> this tunnel. Higher environments (staging, prod) are hosted directly with a DNS CNAME and a
> managed certificate, without a tunnel (see [ARCHITECTURE.md](ARCHITECTURE.md) §7).

The local stack is exposed to users of the Entra tenant through a Cloudflare Tunnel. The
connector dials out to Cloudflare, so no inbound ports are opened on this machine. TLS ends at
Cloudflare's edge with the zone's certificate. The tunnel and its hostnames are **managed in
the Cloudflare dashboard**. The connector runs on the **host** as the Windows service
`Cloudflared`, which holds the tunnel token; the repo holds no tunnel secret.

## Endpoints

| Public hostname | Tunnel service URL (host connector) | Container | Purpose |
|---|---|---|---|
| `app-sdlc-dev.shaheenks.co.in` | `http://localhost:4181` | `oauth2-proxy-public` | Entra sign-in + agent UI (`/dev-ui/`) |
| `mcp-sdlc-dev.shaheenks.co.in` | `http://localhost:8080` | `mcp-bootstrap` | MCP endpoint `/mcp` + OAuth metadata for MCP clients (Antigravity) |
| `api-sdlc-dev.shaheenks.co.in` | *(Stage 8)* | agent API / A2A | Gemini Enterprise / Agent Engine |

Local equivalents (no tunnel): `http://localhost:4180` (sign-in + UI via `oauth2-proxy`) and
`http://localhost:8080` (MCP). Never exposed: Postgres, the agent container, and ADK developer
tools (blocked unless `SDLC_DEV_TOOLS=true`).

The names are one level below `shaheenks.co.in`, so Cloudflare's free Universal SSL certificate
(`*.shaheenks.co.in`) covers them. Deeper names like `app.sdlc.dev.…` would need Advanced
Certificate Manager.

## Setup (once)

1. **Tunnel + connector:** Cloudflare dashboard → Zero Trust → Networks → Tunnels → create a
   **Cloudflared** tunnel, and install the connector on this machine as a Windows service
   (`cloudflared.exe service install <token>`). Run **exactly one connector per tunnel**. A
   second connector (for example a `cloudflared` container) would receive half the traffic
   but couldn't reach `localhost:4181`.
2. **Public hostnames** (tunnel → *Public Hostname*):

   | Subdomain | Domain | Type | URL |
   |---|---|---|---|
   | `app-sdlc-dev` | `shaheenks.co.in` | HTTP | `localhost:4181` |
   | `mcp-sdlc-dev` | `shaheenks.co.in` | HTTP | `localhost:8080` |

   Keep the default HTTP Host header (the original hostname).
3. **Entra:** `sdlc-client` must list `https://app-sdlc-dev.shaheenks.co.in/oauth2/callback`.
   `scripts/entra_setup.ps1` adds it by default, together with the localhost callback.
4. **Start the stack:** `docker compose --profile tunnel up -d --wait`. The `tunnel` profile
   adds `oauth2-proxy-public` on `127.0.0.1:4181`.
5. **Verify:**
   ```bash
   curl https://app-sdlc-dev.shaheenks.co.in/ping          # OK
   curl https://mcp-sdlc-dev.shaheenks.co.in/healthz       # {"status":"ok",...}
   curl -i -X POST https://mcp-sdlc-dev.shaheenks.co.in/mcp -d '{}'   # 401 + resource_metadata
   ```
   Then open https://app-sdlc-dev.shaheenks.co.in and sign in.

## Recommended edge settings (dashboard)

- **SSL/TLS → Edge Certificates:** *Always Use HTTPS* on; HSTS once everything works.
- **Security → WAF → Rate limiting** on both hostnames (for example per-IP limits on `/mcp` and
  `/oauth2/*`), since the endpoints are internet-reachable even though every request needs an
  Entra token or sign-in.
- **Do not put Cloudflare Access in front of `mcp-sdlc-dev`:** MCP clients authenticate with
  Entra OAuth, which an Access login page would break. The app host is already behind Entra
  sign-in; Access there would only add a second login.

## Who can sign in

Only members of the Entra tenant who are **assigned** to the `sdlc-mcp` enterprise app
(assignment is required). Add users with `scripts/entra_setup.ps1` or the Entra admin center.
Guest (B2B) users are out of scope for now.

## Notes

- **The host service runs independently of Docker.** When the stack is down, the public
  hostnames return Cloudflare 502 errors. When the stack moves to another machine, either
  install the connector there or switch to a `cloudflared` container: routes would then use
  Docker service names (`oauth2-proxy-public:4180`, `mcp-bootstrap:8080`), and 4181 need not
  be published.
- The public oauth2-proxy trusts `X-Forwarded-*` headers (reverse-proxy mode) and uses
  `Secure` cookies. It is published on `127.0.0.1` only.
- The edge times out after 100 s with no data. Agent runs stream over SSE (`/run_sse`), so
  long runs keep the connection alive.
- MCP clients outside Docker use `https://mcp-sdlc-dev.shaheenks.co.in/mcp`. The server's 401
  challenge advertises it (`MCP_PUBLIC_URL`).
- Stage 7 (GCP) replaces the tunnel with Cloud Run domains / a load balancer. The hostnames can
  stay the same.
