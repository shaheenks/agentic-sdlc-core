# sdlc_ui

The web UI and its backend-for-frontend (BFF) in one container ([sdlc_ui](../spec/components/sdlc-ui.md);
NFR-ARCH-001, DEC-0010): chat with user_agent (CopilotKit, AG-UI), the user's chats, artifacts and connections.

- Identity (`lib/identity.ts`): the user's account ID and email from IAP's signed assertion, verified on every
  request; locally (`SDLC_ENV=local`) a fixed user instead. Every API route goes through `withUser`.
- Chat (`lib/chat.ts`, `lib/events.ts`): CopilotKit's runtime with an AG-UI agent that streams user_agent's
  answer from Agent Runtime for the verified user. A chat is the user's runtime session; nothing is stored in
  this process, and reopening a chat replays its history from the runtime for the same user.
- Backends (`lib/backends.ts`): Agent Runtime with this service's access token; user_agent_mcp's HTTP API with
  its ID token and the user in `X-SDLC-User-Id` / `X-SDLC-User-Email`; the event gateway's `/simulate` the same way.
- Events (`app/events`, [DEC-0016](../spec/decisions/DEC-0016.md)): simulated events for the event agents until the
  webhooks are set up, shown only to members of a team the environment allows to simulate.

```sh
npm ci
npm run typecheck && npm test && npm run build
```

| Variable | Default | Meaning |
|---|---|---|
| `PORT` | `3000` | Port to listen on (Cloud Run sets it) |
| `SDLC_ENV` | - | Environment name; `local` allows the local settings below |
| `SDLC_AUTH` | `iap` | `iap`, or `local` with `SDLC_LOCAL_USER_ID` and `SDLC_LOCAL_USER_EMAIL` |
| `SDLC_IAP_AUDIENCE` | - | `/projects/<number>/locations/<region>/services/sdlc-ui` |
| `SDLC_AGENT_URL` | - | `https://<region>-aiplatform.googleapis.com/v1/projects/<p>/locations/<region>/reasoningEngines/<id>`, or the local runtime `http://user-agent:8085/v1/local` |
| `SDLC_AGENT_AUTH` | `google` | `none` locally |
| `SDLC_MCP_URL` | - | user_agent_mcp's URL |
| `SDLC_MCP_AUTH` | `id_token` | `none` locally (user_agent_mcp in identity mode `trusted_header`) |
| `SDLC_EVENTS_URL` | - | The event gateway's URL for the Events page (simulated events, DEC-0016); unset hides the page |
| `SDLC_EVENTS_AUTH` | `id_token` | `none` locally (the gateway in identity mode `trusted_header`) |
