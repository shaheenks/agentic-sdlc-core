---
type: Non-Functional Requirement
title: Single enforcement point
description: Authorization is decided only in the MCP server, never in prompts or agent code.
area: Security
tags:
- requirement
- non-functional
- security
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:30:44+05:30'
sources:
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
- Only MCP servers and ingest read configuration, through `ConfigStore.current()`.
