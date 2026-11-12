---
type: Functional Requirement
title: Per-call authorization with argument limits
description: Every tool call is re-authorized, including team limits on argument values.
area: Authorization
tags:
- requirement
- functional
- authorization
status: stable
verified:
- by: human:shaheenks
  at: '2026-11-11T16:02:28+05:30'
priority: must
implementation: live
sources:
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
---

# Statement

The system shall re-check authorization on every tool call, including limits on argument values, regardless of what was listed.

# Acceptance criteria

- Calling a tool that was filtered from the listing is refused.
- Argument limits are unioned across the teams that constrain a tool; a team that does not constrain it never widens access.
- Roles with `tools.unconstrained: true` (admin) skip argument limits.

# Notes

"A deny wins over any allow" is stated once, in [NFR-SEC-002](../non-functional/NFR-SEC-002.md) (CH-0002).
