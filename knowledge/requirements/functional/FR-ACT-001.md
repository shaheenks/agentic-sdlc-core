---
type: Functional Requirement
title: SDLC action tools
description: Tools that review code, generate tests and approve designs.
area: SDLC actions
tags:
- requirement
- functional
- sdlc-actions
status: stable
priority: should
implementation: stub
verified:
- by: human:shaheenks
  at: '2026-11-10T21:28:01+05:30'
sources:
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
---

# Statement

The system shall provide tools that review code, generate tests and approve designs within the caller's repository limits.

# Acceptance criteria

- `review_code`, `generate_tests` and `approve_design` exist in the catalog and enforce `repo` argument limits.
- Real behaviour is to be defined; today they echo their inputs (inventory gap 1).
