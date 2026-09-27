# sdlc_policy

Authorization decisions for MCP tools, from an `EffectivePolicy` (see `sdlc_config.resolve`).
Stage 3.

- `visible_tools(policy, names)`: the tools a user may see (tools/list filtering).
- `authorize(policy, tool, arguments) -> Decision(allowed, reason, matched_rule)`:
  deny by default. A call is refused when the tool is denied (deny wins), not granted, or a
  constrained argument is missing or not in the allowed values.
- Pure functions, no I/O. The MCP server's policy middleware calls them on every
  `tools/list` and `tools/call` and writes `decision` + `matched_rule` to the audit log.

Tests: `tests/policy/`.
