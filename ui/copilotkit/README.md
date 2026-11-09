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
