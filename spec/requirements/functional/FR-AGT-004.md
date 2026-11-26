---
type: Functional Requirement
title: "Event agent MCP server"
description: "Agents in scheduled and event-triggered runs act as the system identity through event_agent_mcp, a standalone MCP server separate from user_agent_mcp."
tags: [requirement, agt, mcp, security]
status: draft
x-area: AGT
x-priority: must
x-implementation: planned
---

# Statement

The system shall provide a standalone MCP server, event_agent_mcp, through which agents in scheduled and event-triggered runs act as the system identity, and which accepts no user token.

# Acceptance criteria

- The event agents (ci_workflow_agent, operations_agent) call it with tokens of the service account of the event agents' own Agent Runtime deployment, which is the system identity; the agents get short-lived Google ID tokens for it from the runtime, with no key or stored token.
- event_agent_mcp accepts only that service account's tokens; any other token, including a user's, is refused
  with 401.
- It receives traffic only from that Agent Runtime deployment: internal ingress, reached through the
  deployment's network attachment, and Cloud Run invoker granted to that service account alone.
- The event-based agents (`event_based_agents/`) connect to event_agent_mcp only ([NFR-ARCH-006](../non-functional/NFR-ARCH-006.md)).
- user_agent_mcp refuses the system identity's token, so unattended runs reach tools only through
  event_agent_mcp ([FR-AGT-003](FR-AGT-003.md)).
- Its tools are the tool groups declared for the system identity in configuration, authorized by the same
  Access Policy as any call; every span, log entry, audit record and event_agent_mcp request of an unattended run carries the event metadata (source system, event type, delivery ID, subject) and the run ID ([NFR-OBS-003](../non-functional/NFR-OBS-003.md)).
- Downstream calls use only system connections ([FR-CONN-004](FR-CONN-004.md)); system connection PATs are GCP Secret Manager secrets given to event_agent_mcp as environment variables; they are long-lived (no expiry and no rotation) and event_agent_mcp uses them to act on Jira, Confluence, Bitbucket, GitHub and the other declared systems. It can read no
  user's connection, artifact or session.
- Its storage access is limited to `artifacts/system/` of the artifact bucket ([DEC-0006](../../decisions/DEC-0006.md)).
- It writes each run's results back to the downstream systems the workflow declares ([FR-TRIG-003](FR-TRIG-003.md)).
- It implements the current stable MCP specification revision (2026-07-28 when this was written).
- It builds, tests and deploys on its own from `mcp_servers/event_agent_mcp/`.
- event_agent_mcp opens pull requests only from `sdlc/` branches into `feature/` branches, has no merge or approve
  tool, and starts the Code Workspace job ([DEC-0015](../../decisions/DEC-0015.md)).

# Notes

Decided in [DEC-0007](../../decisions/DEC-0007.md). Token verification, policy, audit and connector code are shared with user_agent_mcp as libraries under `libs/`, not copied.

# Citations

[1] [MCP specification 2026-07-28: changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
