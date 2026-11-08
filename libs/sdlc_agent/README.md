# sdlc_agent

Shared helpers for ADK agents. Stage 4; version-03 P4, P10.

- `with_team_context(base_instruction, mcp_url)`: an async ADK instruction provider. Once per
  session it calls the MCP tool `get_agent_context` **with the signed-in user's token**
  (`sdlc_auth.adk.get_user_token`) and appends that user's team instructions (AGENT_ADDENDUM)
  and context to the base instruction. Results are cached per (session, user, active team) for
  15 minutes.
- Active team (version-03 P10 G9): `make_set_active_team(mcp_url)` is the agent tool that locks
  one of the user's teams for the conversation's document (checked with
  `get_agent_context(team=)` as the user, kept in session state `ACTIVE_TEAM_KEY`). Without a
  locked team the instruction is broad (all teams named); with one, that team is in full
  (addendum, context, document flow defaults) and the others are named only.
- `goldfish.make_goldfish_review(mcp_url, model)`: isolated Goldfish reviewers (P10): one nested
  run per lens (fresh session, empty state, only the draft), lens text loaded with `load_skill` as
  the user, `search_knowledge` / `graph_query` only, then a tool-less synthesizer (Blocker / Major /
  Nit, each traced to its lens). Lens defaults and caps come from `get_agent_context`
  `flows.document` for the locked team (`doc_type=`); required lenses are always added.
- `a2ui_cards` (P4): `after_tool_callback` builds A2UI v0.9 cards (citations, whoami, connected
  tools; strict validation, `http(s)` links only) from tool results and drops forged ones;
  `before_model_callback` keeps them out of the model's view. A2A sends them as DataParts.
- Team instructions are **guidance, not permissions**: access is enforced by the MCP server.
  If the call fails, the agent continues with the base instruction (logged).
- Agents never read `config/`; they only see what the MCP server returns for the user.
