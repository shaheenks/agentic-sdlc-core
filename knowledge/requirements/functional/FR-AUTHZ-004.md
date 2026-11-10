---
type: Functional Requirement
title: Per-user rate limits
description: Calls are rate-limited per user from a platform baseline and team limits.
area: Authorization
tags:
- requirement
- functional
- authorization
status: stable
priority: should
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:10:40+05:30'
sources:
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
---

# Statement

The system shall limit each user's call rate, overall and per tool, from a platform baseline and team limits.

# Acceptance criteria

- When a user is in several teams, the most generous team limit applies.
- Limits are enforced after authorization and a refusal is audited with `outcome: rate_limited` and the rule.

# Notes

Counters are held in memory per MCP instance. A shared store is needed before `sdlc-mcp` runs more than one instance; see [NFR-REL-003](../non-functional/NFR-REL-003.md).
