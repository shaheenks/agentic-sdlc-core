---
type: Non-Functional Requirement
title: Scale-out readiness
description: Per-instance state must move to shared stores before services run more than one instance.
area: Reliability
tags:
- requirement
- non-functional
- reliability
status: stable
priority: could
implementation: planned
verified:
- by: human:shaheenks
  at: '2026-11-10T21:45:18+05:30'
sources:
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: v03
  resource: ../../../docs/plans/version-03.md
  title: Implementation plan version-03
---

# Statement

The system shall behave the same when a service runs on more than one instance.

# Acceptance criteria

- Rate-limit counters are held in a shared store (today: in memory per MCP instance; inventory gap 11).
- A2A task and context owner maps are shared (today: per instance; inventory gap 10).
