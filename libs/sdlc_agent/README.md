# sdlc_agent

Shared helpers for ADK agents. Stage 4.

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
- `goldfish.make_goldfish_review(mcp_url, model)`: isolated Goldfish reviewers (P10); lens
  defaults and caps come from `get_agent_context` `flows.document` for the locked team.
- Team instructions are **guidance, not permissions**: access is enforced by the MCP server.
  If the call fails, the agent continues with the base instruction (logged).
- Agents never read `config/`; they only see what the MCP server returns for the user.
