# agents/user_agent

The interactive root agent (ADK, Gemini on Vertex AI): the agent behind the chat app, the dev UI and A2A.

- **MCP toolset** with `agent_header_provider` (the user's token + the conversation id): every MCP tool the user
  may see, nothing else.
- **Instruction** via `with_team_context`: broad (all the user's teams) until a team is locked for a document,
  then that team in full (addendum, context, document-flow defaults).
- **Local tools:** `goldfish_review` (isolated reviewers of the EGM document flow) and `set_active_team`.
- **Callbacks:** A2UI cards attached to tool results for A2A clients (`after_tool_callback`), hidden from the
  model (`before_model_callback`).

Served by `sdlc-agent-web` (`libs/sdlc_web`). Stages 1, 2, 4; version-03 P4, P10.
