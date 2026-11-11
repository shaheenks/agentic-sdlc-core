---
type: Non-Functional Requirement
title: Fail closed
description: Missing or unverifiable identity or configuration means less access, never more.
area: Security
tags:
- requirement
- non-functional
- security
status: draft
priority: must
implementation: live
sources:
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

When identity or configuration cannot be verified, the system shall refuse rather than fall back to wider access.

# Acceptance criteria

- The MCP server refuses to start without valid configuration and the Entra tenant and client IDs.
- If the signing keys (JWKS) cannot be reached, every request is refused.

# Notes

The overage rule (a token without groups yields no groups) is stated once, in [FR-IDN-002](../functional/FR-IDN-002.md) (CH-0002).
