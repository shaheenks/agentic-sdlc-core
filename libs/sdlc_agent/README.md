# sdlc_agent

Shared helpers for ADK agents. Stage 4.

- `with_team_context(base_instruction, mcp_url)`: an async ADK instruction provider. Once per
  session it calls the MCP tool `get_agent_context` **with the signed-in user's token**
  (`sdlc_auth.adk.get_user_token`) and appends that user's team instructions (AGENT_ADDENDUM)
  and context to the base instruction. Results are cached per (session, user) for 15 minutes.
- Team instructions are **guidance, not permissions**: access is enforced by the MCP server.
  If the call fails, the agent continues with the base instruction (logged).
- Agents never read `config/`; they only see what the MCP server returns for the user.
