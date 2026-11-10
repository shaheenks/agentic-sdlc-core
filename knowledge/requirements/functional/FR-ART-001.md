---
type: Functional Requirement
title: Save and manage artifacts
description: The assistant saves documents for a user; only the owner can list, read or delete them.
area: Artifacts
tags:
- requirement
- functional
- artifacts
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:13:57+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
---

# Statement

The system shall store documents the assistant saves for a user and restrict them to their owner.

# Acceptance criteria

- The owner is the token `oid`, never a tool argument.
- Another user's artifact id answers 'artifact not found'.
- Artifacts are text only, at most 1 MiB each and 50 per user.
