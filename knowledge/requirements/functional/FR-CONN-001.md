---
type: Functional Requirement
title: Users connect their own accounts
description: Users add personal access tokens for external systems through a dedicated page, never through chat.
area: Connections
tags:
- requirement
- functional
- connections
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:28:01+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
---

# Statement

The system shall let users connect their own accounts on external systems through a dedicated interface and keep those credentials per user.

# Acceptance criteria

- Tokens are added and removed through the `/connections/` API (Connections page), never through chat.
- Tokens live only in the per-user secret store, read and written only by the MCP server.
- The user is warned when a token expires within 14 days.
- Each change is audited as `connection_change`.
