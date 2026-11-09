# sdlc_web

Serves ADK agents (dev UI + API from `get_fast_api_app`, AG-UI, A2A) to signed-in Entra users. Stage 2d;
version-01 M5/M8, version-02 N8/N15, version-03 P4.
Runs in the agent container as `sdlc-agent-web`, behind oauth2-proxy:

```
browser -> oauth2-proxy :4180 (Entra sign-in, PKCE; X-Forwarded-Access-Token)
        -> sdlc-agent-web :8000 (EntraUserBindingMiddleware -> ADK web app)
        -> agent McpToolset (agent_header_provider) -> MCP server (validates the same token)
```

`EntraUserBindingMiddleware`:
- **Re-validates** the forwarded token (Entra v2, `access_as_user`, tenant, user token), so a
  forged header gets 401 even if the proxy is bypassed.
- **Binds ADK's user id to the token `oid`** in `/apps/{app}/users/{user_id}/...` and in `/run`
  and `/run_sse` bodies, so users only see their own sessions.
- **Sets the token in a request-scoped ContextVar** (`sdlc_auth.adk`). ADK runs the agent in a
  task created within the request, so `agent_header_provider` sees it. The token is never stored
  in session state, and a `state_delta` trying to inject one is dropped.
- **Restricts ADK developer tools (`/dev/*`)** to what the chat UI needs: graph views,
  user-bound routes, and the trace of the caller's **own** session (checked with an internal
  session lookup). Builder save, deploy, evals, tests and event traces get 403, and the UI's
  load-time listings return `[]`. `SDLC_DEV_TOOLS=true` re-enables them for local development only.
- **Binds WebSocket `/run_live`** the same way (token from the upgrade request, `user_id` replaced
  by the `oid`); any other WebSocket is closed with 1008. `/healthz` is public.
- **Drops client-sent state** it must own: `temp:` / `app:` / `user:` keys and every `sdlc_` key
  (e.g. the locked team `sdlc_active_team`) in AG-UI state and `/run` `state_delta`.
- `GET /me` (display name + sign-in name only, for the chat navbar); `GET /` redirects to the chat
  app (`/chat/`).

Other modules:

| Module | What it does |
|---|---|
| `agui.py` | AG-UI endpoint `/agui` (`ag_ui_adk`) for the CopilotKit chat, user id = token `oid` |
| `a2a.py` | A2A endpoint `/a2a` (A2A 0.3 JSON-RPC, version-03 P4) + public `/.well-known/agent-card.json`, on when `SDLC_A2A_AGENT` names the agent (`SDLC_A2A_URL` = advertised URL). Call context = verified `oid`; text parts only; another user's task / context = not found; A2UI cards as `application/json+a2ui` DataParts |
| `threads.py` | `GET /threads` (the caller's conversations, for the chat sidebar), `DELETE /threads/{id}` (own chats only, needs `X-SDLC-Request: 1`; others answer 404) |
| `sessions.py` | Agent Engine session store (`agentengine://…`) with a TTL of `SDLC_SESSION_RETENTION_DAYS` from conversation start |
| `retention.py` | SQLite store: deletes conversations idle longer than the retention, at startup and daily |
| `keepalive.py` | `SseKeepAliveMiddleware`: `: keep-alive` comments after 15 s idle on SSE streams (long Goldfish reviews through the tunnel) |

Env: `ENTRA_TENANT_ID`, `ENTRA_API_CLIENT_ID` (required; fail closed), `SDLC_AGENTS_DIR`,
`SDLC_SESSION_SERVICE_URI` (default `memory://`; compose: SQLite on the agent-only volume; GCP: Agent
Engine), `SDLC_SESSION_RETENTION_DAYS`, `SDLC_A2A_AGENT`, `SDLC_A2A_URL`, `SDLC_DEV_TOOLS`, `HOST`, `PORT`.
Agents never read `config/`. Tests: `tests/web/`.
