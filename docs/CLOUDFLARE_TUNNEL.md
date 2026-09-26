# Public endpoints: Cloudflare Tunnel

The local stack is exposed to users of the Entra tenant through a Cloudflare Tunnel. The
`cloudflared` container dials out to Cloudflare, so no inbound ports are opened on this machine.
TLS ends at Cloudflare's edge with the zone's certificate. The tunnel is **token-based and
managed in the Cloudflare dashboard**; the repo only holds the token (in `.env`).

## Endpoints

| Public hostname | Tunnel service (Docker network) | Purpose |
|---|---|---|
| `app-sdlc-dev.shaheenks.co.in` | `http://oauth2-proxy-public:4180` | Entra sign-in + agent UI (`/dev-ui/`) |
| `mcp-sdlc-dev.shaheenks.co.in` | `http://mcp-bootstrap:8080` | MCP endpoint `/mcp` + OAuth metadata for MCP clients (Antigravity) |
| `api-sdlc-dev.shaheenks.co.in` | *(Stage 8)* agent API / A2A | Gemini Enterprise / Agent Engine |

Local equivalents (no tunnel): `http://localhost:4180` (sign-in + UI, served by `oauth2-proxy`)
and `http://localhost:8080` (MCP). Never exposed: Postgres, the agent container, and ADK developer
tools (blocked unless `SDLC_DEV_TOOLS=true`).

The names are one level below `shaheenks.co.in`, so Cloudflare's free Universal SSL certificate
(`*.shaheenks.co.in`) covers them. Deeper names like `app.sdlc.dev.…` would need Advanced
Certificate Manager.

## Setup (once)

1. **Create the tunnel:** Cloudflare dashboard → Zero Trust → Networks → Tunnels → *Create a
   tunnel* → type **Cloudflared** → name `sdlc-dev`. Copy the token from the install command
   (the long value after `--token`) into `.env`:
   ```dotenv
   CLOUDFLARE_TUNNEL_TOKEN=<token>
   ```
   Skip the connector install step: the connector runs as the `cloudflared` container.
2. **Add the public hostnames** (tunnel → *Public Hostname* tab):

   | Subdomain | Domain | Service type | URL |
   |---|---|---|---|
   | `app-sdlc-dev` | `shaheenks.co.in` | HTTP | `oauth2-proxy-public:4180` |
   | `mcp-sdlc-dev` | `shaheenks.co.in` | HTTP | `mcp-bootstrap:8080` |

   Keep the default HTTP Host header (the original hostname). The DNS records are created
   automatically.
3. **Entra:** `sdlc-client` must list `https://app-sdlc-dev.shaheenks.co.in/oauth2/callback`.
   `scripts/entra_setup.ps1` adds it by default, together with the localhost callback.
4. **Start:** `docker compose --profile tunnel up -d --wait`. The `tunnel` profile adds
   `oauth2-proxy-public` and `cloudflared`. Check the connector with
   `docker compose logs cloudflared` ("Registered tunnel connection"); the dashboard should
   show the tunnel as *Healthy*.

## Recommended edge settings (dashboard)

- **SSL/TLS → Edge Certificates:** *Always Use HTTPS* on; HSTS once everything works.
- **Security → WAF → Rate limiting** on both hostnames (e.g. per-IP limits on `/mcp` and
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

- Request timeout at the edge is 100 s without data. Agent runs stream over SSE (`/run_sse`),
  so long runs keep the connection alive.
- The public oauth2-proxy uses `Secure` cookies and trusts `X-Forwarded-*` headers; it is not
  published on the host, so only `cloudflared` (and containers on the Docker network) reach it.
- For MCP clients outside Docker, point them at `https://mcp-sdlc-dev.shaheenks.co.in/mcp`.
  The server's 401 challenge advertises this URL in its OAuth metadata (`MCP_PUBLIC_URL`).
- Stage 7 (GCP) replaces the tunnel with Cloud Run domains / a load balancer. The hostnames can
  stay the same.
