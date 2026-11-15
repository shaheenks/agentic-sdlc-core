# ui/copilotkit

The CopilotKit chat app for the SDLC agents (version-01 M5; history version-02 N15; artifacts and review
version-03 P5). Next.js 16 + CopilotKit v2, served behind
oauth2-proxy at **`/chat/`** (http://localhost:4180/chat/ locally, `https://app-sdlc-dev…/chat/` via the tunnel).
adk web keeps working at `/dev-ui/`.

```
browser ── cookie ──> oauth2-proxy ── X-Forwarded-Access-Token ──> this app (/chat)
                                                                      │ CopilotKit runtime (server side)
                                                                      └─ AG-UI, same header only ──> agent /agui
                                                                                                       └─ MCP as the user
```

| File | What |
|---|---|
| `lib/runtime.ts` | `CopilotRuntime` with one `HttpAgent` (`SDLC_AGUI_URL`, the agent's internal `/agui`); `forwardHeaders: { allow: ["x-forwarded-access-token"] }` so only the proxy's token header is forwarded (no cookies, no browser `Authorization`, no `x-forwarded-for`) |
| `lib/runner.ts` | `PassThroughAgentRunner`: stores nothing in this process. CopilotKit's `InMemoryAgentRunner` keeps all threads in one process-wide map keyed by thread id and replays them on `connect`, which would let one user read another's conversation; history lives in the agent's per-user session store instead |
| `app/api/copilotkit/[[...slug]]/route.ts` | The runtime handler (Next strips the `/chat` basePath; the route puts it back) |
| `components/renderers.tsx`, `lib/results.ts` | Tool-call rendering only (compact): `search_knowledge` / `graph_query` as citation chips (title, link, source, lines/pages, "exact match" for keyword hits), `whoami` as a collapsed identity line, connected-tool cards, artifact cards (`save_artifact` / `list_artifacts`, links built from the UUID only), the `goldfish_review` card (lens outcomes, blocker / major / nit counts), the `set_active_team` line. Links only `http(s)`. No frontend tools. A2UI cards from the agent are ignored here (they are for A2A clients) |
| `components/ThreadList.tsx`, `lib/threads.ts` | History sidebar: the caller's chats from the agent's `GET /threads`, open (replayed by `PassThroughAgentRunner.connect`), delete (`X-SDLC-Request: 1`) |
| `components/UserStatus.tsx`, `lib/status.ts`, `app/connections/` | Navbar user (`GET /me`) + connection status; Connections page (add / remove PATs through the MCP `/connections/` API) |
| `components/ArtifactsPanel.tsx` | The caller's saved documents from `GET /artifacts/`: download, delete (with confirmation), refresh when the chat saves one |
| `components/ArtifactViewer.tsx`, `ArtifactReviewHost.tsx`, `lib/review.ts` | Overlay viewer: numbered lines + Markdown preview (no raw HTML or images), inline line comments, version picker (older versions read-only), "Attach to chat" = one user message with the reference + comments |
| `lib/keepalive.ts` | SSE keep-alive comments to the browser during long runs (Goldfish reviews through the tunnel) |

## Native GCP stack (CH-0016)

With `SDLC_AGENT_BACKEND=agent-runtime` (Cloud Run service `sdlc-ui-native`, started as `node native-entry.mjs`)
there is no oauth2-proxy: IAP is in front, and the app signs the user in itself.

```
browser ── IAP (Cloud Identity, Entra federation) ──> native-entry.mjs ──> this app
   │ /chat/auth/*: Google code flow for the IAP user; ID + refresh token in a sealed httpOnly cookie
   └ every call: IAP assertion + session -> the user's Google ID token (same user, checked)
        ├─ /chat/api/copilotkit ── user_token ──> Agent Runtime stream_query / get_thread (as the UI's account)
        ├─ /threads, /me ──> Agent Runtime list_threads / delete_thread, the verified identity
        └─ /connections/, /artifacts/ ── Authorization: user token, X-Serverless-Authorization: UI ──> sdlc-mcp-native
```

| File | What |
|---|---|
| `lib/identity.ts`, `lib/jwt.ts` | IAP assertion (ES256) and Google ID token (RS256) checks on the providers' JWKS; the token must name the IAP user |
| `lib/session.ts`, `lib/auth-routes.ts`, `app/auth/*` | Server-side sign-in (PKCE, state, `prompt=none` + `login_hint`; consent once if no refresh token), AES-256-GCM sealed cookies bound to the IAP user, renewal |
| `lib/native.ts` | `resolveUser`: run before anything is done for a user; the verified token replaces any client-sent token header |
| `lib/agent-runtime.ts`, `lib/gcp.ts` | `AgentRuntimeAgent` (AG-UI over `stream_query`, ADK -> AG-UI events, refusals -> `RUN_ERROR`), the engine client, the service account's tokens from the metadata server |
| `lib/native-api.ts`, `app/api/native/*`, `native-entry.mjs` | `/me`, `/threads`, `/connections/`, `/artifacts/` without oauth2-proxy |

Settings (Terraform, `infra/gcp/ui_native.tf`): `SDLC_AGENT_ENGINE`, `SDLC_IAP_AUDIENCE`, `SDLC_OAUTH_CLIENT_IDS`,
`SDLC_ALLOWED_DOMAINS`, `SDLC_GOOGLE_WEB_CLIENT_ID`, `SDLC_PUBLIC_URL`, `SDLC_MCP_BASE_URL`; secrets
`SDLC_GOOGLE_WEB_CLIENT_SECRET`, `SDLC_SESSION_KEY`. Anything missing: the native routes fail closed.
| `next.config.ts` | `basePath: "/chat"`, standalone output, CSP `connect-src 'self'` (no third-party calls from the browser) |

Rules (version-01 §3.2): the token never reaches browser JavaScript and is never logged or stored here; frontend
tools are UI-only (anything that reads data or acts is an MCP tool); telemetry is off (`COPILOTKIT_TELEMETRY_DISABLED`,
`DO_NOT_TRACK`, `NEXT_TELEMETRY_DISABLED`). Versions are pinned exactly in `package.json`.

## Develop

```powershell
cd ui/copilotkit
npm ci
npm test          # results parsing + the real runtime handler against a fake /agui (header allowlist, no replay)
npm run typecheck
npm run build
```

In Docker: `docker compose up -d --build --wait` (service `ui-copilotkit`, internal port 3000, reached only via the proxy).
