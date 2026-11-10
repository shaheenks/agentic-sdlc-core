---
type: Non-Functional Requirement
title: Single enforcement point
description: Authorization is decided only in the MCP server, never in prompts or agent code.
area: Security
tags:
- requirement
- non-functional
- security
status: draft
priority: must
implementation: live
sources:
- id: design
  resource: ../../../docs/designs/workflow-platform.md
  title: Workflow platform target design
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
- id: arch
  resource: ../../../docs/ARCHITECTURE.md
  title: System architecture
---

# Statement

Authorization shall be decided and enforced only in the MCP server.

# Acceptance criteria

- Agents make no authorization decisions, never read `config/` and hold no database credentials.
- Team instructions and skills are guidance and never grant access.
- Only MCP servers and ingest read configuration, through `ConfigStore.current()`. The event gateway reads only the `Trigger` kind, the same way.
- An agent gateway, when used, may only narrow what the MCP server allows; it never grants access.
- Event enrichment, workflow runtimes and delivery make no authorization decisions; they reach tools and data only through the MCP server.

# Notes

Modified by CH-0008: the event workflows and the optional Agent Gateway of the target design.
