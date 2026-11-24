---
type: Non-Functional Requirement
title: "Two MCP servers, one per class of caller"
description: "The platform always has exactly two MCP servers, user_agent_mcp and event_agent_mcp, classified by nature of usage, access pattern, capabilities and configuration; each agent deployment connects only to its own."
tags: [requirement, arch, mcp, security]
status: draft
x-area: ARCH
x-priority: must
x-implementation: planned
---

# Statement

The system shall have exactly two MCP servers, user_agent_mcp and event_agent_mcp, separated by the nature of their usage, their access patterns, their capabilities and their configuration, and each agent deployment shall connect only to its own server.

# Acceptance criteria

- Nature of usage: user_agent_mcp serves work done for a signed-in user (the interactive agents and, once enabled, coding harnesses); event_agent_mcp serves unattended work started by schedules and events (the event-based agents).
- Access pattern: user_agent_mcp accepts only users' Google tokens, from the interactive Agent Runtime deployment and from declared harness clients; event_agent_mcp accepts only the event-based agents' service-account tokens, on internal ingress from that Agent Runtime deployment.
- Capabilities: user_agent_mcp works on the user's own artifacts, connections, knowledge scope, workflows and tasks; event_agent_mcp works with system connections and `artifacts/system/`, and writes results back to downstream systems.
- Configuration: each server has its own service account, storage prefixes, secrets delivery (encrypted per-user secrets in the bucket, or environment variables from Secret Manager) and tool groups declared in `config/`.
- The interactive agents (`interactive_agents/user_agent/`) call only user_agent_mcp ([FR-AGT-003](../functional/FR-AGT-003.md)); the event-based agents (`event_based_agents/`) call only event_agent_mcp ([FR-AGT-004](../functional/FR-AGT-004.md)). Each server refuses the other class's tokens.
- A new caller is assigned to one of the two servers by its class; adding a third MCP server needs a new decision record.
- Both share token verification, policy, audit and connector code through `libs/` ([DEC-0005](../../decisions/DEC-0005.md)).

# Notes

Decided in [DEC-0002](../../decisions/DEC-0002.md) and [DEC-0007](../../decisions/DEC-0007.md).
