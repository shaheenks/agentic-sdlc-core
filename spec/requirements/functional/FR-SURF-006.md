---
type: Functional Requirement
title: "Direct MCP access from coding harnesses"
description: "Coding harnesses such as Google Antigravity, Gemini CLI and Claude Code connect directly to user_agent_mcp with the user's Google account token, using only the tool groups declared for them."
tags: [requirement, surfaces]
status: draft
x-area: SURF
x-priority: must
x-implementation: parked
---

# Statement

The system shall expose user_agent_mcp for direct access by coding harnesses such as Google Antigravity, Gemini CLI and Claude Code,
acting with the user's own Google account token, and give each harness only the tool groups declared for it.

# Acceptance criteria

- Only user_agent_mcp is reachable from coding harnesses; event_agent_mcp never is
  ([NFR-ARCH-006](../non-functional/NFR-ARCH-006.md)).
- Every request carries a Google token of the user's own account, issued to an OAuth client declared for the
  harness surface in configuration. A request without one, with a service-account token, or with a token of an
  undeclared client is refused with 401.
- The user ID is taken from the verified token and scopes every call, as on any other surface
  ([FR-AUTHZ-008](FR-AUTHZ-008.md)).
- A harness sees only the tool groups declared for its surface ([FR-AUTHZ-006](FR-AUTHZ-006.md)), for example:
  list the workflows the user may start, describe a workflow's inputs, start, follow and cancel a run, list and
  answer the user's own tasks, search knowledge, and read the user's artifacts. Connection management and secret
  entry stay in sdlc_ui unless declared otherwise.
- `start_run` returns as soon as the run is accepted, with its run ID; the harness follows the run with `get_run`.
- The server follows the MCP authorization specification: it publishes OAuth protected-resource metadata that
  names Google as the authorization server, and answers a request without a valid token with 401.
- A run started from a harness records the surface's name, appears in the user's run history in sdlc_ui, and is
  subject to the same permissions as on any other surface.

# Notes

- Parked: Gemini Enterprise is the only AI surface for now.
- A harness sends the user's own Google account token directly (from the user's Google sign-in in the
  harness, issued to an OAuth client declared for that harness); user_agent_mcp verifies it as for any other
  surface. No IAP sits in front of this path. A shared API key is not an option.
- Parked with this surface: an IAP desktop client (an internal *Desktop app* OAuth client allowed for IAP
  programmatic access) as an extra gate in front of user_agent_mcp.
- Harnesses reach the platform through user_agent_mcp only; they do not need the A2A router.
- Served by [user_agent_mcp](../../components/user-agent-mcp.md) ([DEC-0002](../../decisions/DEC-0002.md)).

# Citations

[1] [Antigravity: use MCP servers](https://docs.cloud.google.com/data-cloud-extension/antigravity/use-mcp-servers)
[2] [MCP specification: authorization](https://modelcontextprotocol.io/specification/latest/basic/authorization)
