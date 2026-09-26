# sdlc_web

Serves ADK agents (dev UI + API from `get_fast_api_app`) to signed-in Entra users. Stage 2d.
Runs in the agent container as `sdlc-agent-web`, behind oauth2-proxy:

```
browser -> oauth2-proxy :4180 (Entra sign-in, PKCE; X-Forwarded-Access-Token)
        -> sdlc-agent-web :8000 (EntraUserBindingMiddleware -> ADK web app)
        -> agent McpToolset (bearer_header_provider) -> MCP server (validates the same token)
```

`EntraUserBindingMiddleware` does four things:
- **Re-validates** the forwarded token (Entra v2, `access_as_user`, tenant, user token), so a
  forged header gets 401 even if the proxy is bypassed.
- **Binds ADK's user id to the token `oid`** in `/apps/{app}/users/{user_id}/...` and in `/run`
  and `/run_sse` bodies, so users only see their own sessions.
- **Sets the token in a request-scoped ContextVar** (`sdlc_auth.adk`). ADK runs the agent in a
  task created within the request, so `bearer_header_provider` sees it. The token is never stored
  in session state, and a `state_delta` trying to inject one is dropped.
- **Refuses WebSocket `/run_live`** until it can be bound the same way. `/healthz` is public.

Env: `ENTRA_TENANT_ID`, `ENTRA_API_CLIENT_ID` (required; fail closed), `SDLC_AGENTS_DIR`,
`SDLC_SESSION_SERVICE_URI` (default `memory://`; sessions are lost on restart until Stage 7),
`HOST`, `PORT`. Agents never read `config/`. Tests: `tests/web/`.
