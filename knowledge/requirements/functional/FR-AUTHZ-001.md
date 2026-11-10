---
type: Functional Requirement
title: Selective disclosure of tools
description: tools/list returns only the tools the caller's effective policy allows.
area: Authorization
tags:
- requirement
- functional
- authorization
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:10:40+05:30'
sources:
- id: arch
  resource: ../../../docs/ARCHITECTURE.md
  title: System architecture
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

The system shall list to each user only the tools their effective policy allows.

# Acceptance criteria

- Two personas with different roles receive different `tools/list` results from the same server.
- Every catalog tool has persona-matrix rows in `tests/policy/matrix.yaml`; a test fails if one has none.
- The listing is audited as `tools_list` with visible names and a hidden count.
