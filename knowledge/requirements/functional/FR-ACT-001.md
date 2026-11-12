---
type: Functional Requirement
title: SDLC action tools
description: Tools that review code, generate tests and approve designs.
area: SDLC actions
tags:
- requirement
- functional
- sdlc-actions
status: deprecated
priority: should
implementation: parked
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

# Notes

Retired by CH-0003 on 2026-11-11: the three tools only echoed their input and were removed from
the catalog, the roles, the teams and the code. Real action tools come with the write tools
(version-03 P7, FR-WRITE-001) under new IDs. This ID is not reused.
