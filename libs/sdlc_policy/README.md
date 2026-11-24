# sdlc_policy

The Access Policy ([component](../../spec/components/access-policy.md); FR-AUTHZ-001 to FR-AUTHZ-007,
FR-TEAM-002): the effective policy from declared grants and the surface's tool groups, decided deny by default
with the matching rule named, and approximate per-instance rate limits on tool calls. Shared by user_agent_mcp
and, from phase 5, event_agent_mcp (DEC-0005). Test from this folder: `uv run pytest`.
