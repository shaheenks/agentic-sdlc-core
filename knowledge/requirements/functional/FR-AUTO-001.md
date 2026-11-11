---
type: Functional Requirement
title: Autonomous agents and event intake
description: CI and operations agents run on events under their own workload identity.
area: Autonomous agents
tags:
- requirement
- functional
- autonomous-agents
status: deprecated
priority: could
implementation: planned
sources:
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: v03
  resource: ../../../docs/plans/version-03.md
  title: Implementation plan version-03
---

# Statement

The system shall run agents triggered by events, under their own workload identity, that read and report back.

# Acceptance criteria

- To be defined when the milestone is confirmed (version-03 P6).

# Notes

Retired by CH-0008 (2026-11-11). Replaced by [FR-WFL-002](FR-WFL-002.md) event intake, [FR-WFL-003](FR-WFL-003.md) enrichment, [FR-WFL-004](FR-WFL-004.md) build and test, [FR-WFL-005](FR-WFL-005.md) deploy and maintain, and [FR-IDN-005](FR-IDN-005.md) workflow identity.
