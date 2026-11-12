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
verified:
- by: human:shaheenks
  at: '2026-11-11T16:02:28+05:30'
priority: must
implementation: live
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
- The listing is audited as `tools_list` with visible names and a hidden count.

# Notes

Persona-matrix coverage of every tool is stated once, in [NFR-MAINT-002](../non-functional/NFR-MAINT-002.md) (CH-0002).
