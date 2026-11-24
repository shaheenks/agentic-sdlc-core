---
type: Functional Requirement
title: "User agent MCP server"
description: "Agents on Agent Runtime act for the user through user_agent_mcp, which scopes every action to the user in the verified token."
tags: [requirement, agent-steps]
status: draft
x-area: AGT
x-priority: must
x-implementation: planned
---

# Statement

The system shall provide a dedicated MCP server, user_agent_mcp, through which agents running on Agent Runtime
act on behalf of the user, verifying the user's access token on every request and scoping every action to the
user ID that token identifies.

# Acceptance criteria

- Every request carries the user's access token as a bearer token, forwarded by the agent; a request without
  one, or with a service credential in its place, is refused with 401.
- The user ID is taken from the verified token, never from a tool argument. No tool accepts a user ID.
- A tool can read or change only resources owned by that user, or shared with them as policy allows. A request
  for anyone else's resource is answered as not found, so it does not reveal that the resource exists.
- Tools include: save, read, list and delete artifacts; list connections and their status, start a new or
  replacement connection, test and revoke a connection; and show the caller's own identity and effective access.
- The interactive agents (`interactive_agents/user_agent/`) connect to user_agent_mcp only ([NFR-ARCH-006](../non-functional/NFR-ARCH-006.md)).
- It implements the current stable MCP specification revision (2026-07-28 when this was written).
- Every call is authorized by the Access Policy for that user and surface and audited with the user ID, tool,
  decision and run, never with argument values.

# Notes

- Google access tokens carry Google's own OAuth scopes, not scopes the platform defines, so what a caller may do
  is decided by the Access Policy for the verified user, not by token scopes.
- The same server is to serve coding harnesses directly, with their own tool groups
  ([FR-SURF-006](../functional/FR-SURF-006.md), [DEC-0002](../../decisions/DEC-0002.md)); that surface is parked for now.
- It accepts user tokens only. Scheduled and event-triggered runs use event_agent_mcp
  ([FR-AGT-004](FR-AGT-004.md), [DEC-0007](../../decisions/DEC-0007.md)).
- Code lives in `mcp_servers/user_agent_mcp/`.

# Citations

[1] [MCP specification 2026-07-28: changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
