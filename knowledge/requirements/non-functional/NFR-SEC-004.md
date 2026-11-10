---
type: Non-Functional Requirement
title: Fail closed
description: Missing or unverifiable identity or configuration means less access, never more.
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
  resource: ../../../CLAUDE.md
  title: Project rules
---

# Statement

When identity or configuration cannot be verified, the system shall refuse rather than fall back to wider access.

# Acceptance criteria

- The MCP server refuses to start without valid configuration and the Entra tenant and client IDs.
- A token without groups (overage) yields no groups.
- If the signing keys (JWKS) cannot be reached, every request is refused.
