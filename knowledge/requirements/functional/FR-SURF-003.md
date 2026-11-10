---
type: Functional Requirement
title: Direct MCP clients
description: IDE clients can connect straight to the MCP server.
area: Surfaces
tags:
- requirement
- functional
- surfaces
status: stable
priority: could
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:28:01+05:30'
sources:
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: arch
  resource: ../../../docs/ARCHITECTURE.md
  title: System architecture
---

# Statement

The system shall let MCP-capable clients such as IDEs connect directly to the MCP server under the same checks as any other caller.

# Acceptance criteria

- The MCP server speaks streamable HTTP and applies token validation and policy to direct clients.

# Notes

Verified with a developer token only; OAuth sign-in from the IDE is proposed in version-03 P9.
