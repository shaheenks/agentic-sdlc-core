# user_agent

The interactive agent ([user_agent](../../spec/components/user-agent.md), [Agent Runtime](../../spec/components/agent-runtime.md);
FR-AGT-005, DEC-0004, DEC-0010): ad-hoc knowledge search and brainstorming for the signed-in user, on Agent
Runtime. Every tool is a user_agent_mcp tool, listed and allowed for the user by user_agent_mcp.

- `agent.py`: the ADK agent (Gemini through Vertex AI; the model runs in `eu`, the runtime in europe-west3).
  A chat is titled from its first message (session state `sdlc_title`).
- `identity.py`: each call to user_agent_mcp carries the session's user (`X-SDLC-User-Id`, and
  `X-SDLC-User-Email` from state `sdlc_user_email`, which sdlc_ui sets when it creates the session) and this
  runtime's own ID token. A session without both is sent without them and refused (fail closed).
- `runtime.py`: the Agent Runtime application: `AdkApp` with only the operations sdlc_ui needs; a query must
  name an existing session of the same user and cannot inject events.
- `deploy.py`: stages and deploys to Agent Runtime, as the interactive agents' service account.
- `python -m user_agent`: the same operations served locally in Agent Runtime's request shape (Docker Compose).

```sh
uv run python interactive_agents/user_agent/deploy.py --env dev --dry-run   # from the repository root
uv run python interactive_agents/user_agent/deploy.py --env dev             # commit first
```

Build and test from this folder: `uv run pytest`.

| Variable | Default | Meaning |
|---|---|---|
| `SDLC_MCP_URL` | `http://127.0.0.1:8080/mcp` | user_agent_mcp's MCP endpoint |
| `SDLC_MCP_AUDIENCE` | `SDLC_MCP_URL` | Audience of the runtime's ID token (user_agent_mcp's `PUBLIC_URL`) |
| `SDLC_CALLER_AUTH` | `id_token` | `none`: no ID token, for a local user_agent_mcp in identity mode `trusted_header` |
| `SDLC_MCP_TIMEOUT` | `30` | Seconds per MCP call (a scaled-to-zero server needs a few) |
| `SDLC_AGENT_MODEL` | `gemini-3.8-flash` | The model of the chat, drafting and revising |
| `SDLC_REVIEW_MODEL` | `gemini-3.5-flash` | The model of the seven reviewers |
| `SDLC_MODEL_LOCATION` | `eu` | Vertex AI location of the model |
| `GOOGLE_CLOUD_PROJECT` | - | Project for Vertex AI (set by Agent Runtime) |
| `PORT` | `8085` | Local server only |
