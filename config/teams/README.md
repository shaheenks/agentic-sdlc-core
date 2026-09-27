# config/teams

kind: Team — membership (group alias → roles), policy.tools (deny, constraints), policy.limits (per-user
calls per minute: `calls_per_minute` for all tools, `tools.<tool>.calls_per_minute` on top), addons (skills,
instructions, context).

Rate limits: the most generous value across a user's teams applies per scope; without a team value the
`platform.yaml` `defaults.rate_limit` baseline applies to all tools. Limits apply to every role (admin included),
are checked after authorization (refused calls do not count), and are counted per MCP server instance.
