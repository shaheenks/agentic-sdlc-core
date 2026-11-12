---
type: Functional Requirement
title: Save and manage artifacts
description: The assistant saves documents for a user; only the owner can list, read or delete them.
area: Artifacts
tags:
- requirement
- functional
- artifacts
status: draft
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

The system shall store documents the assistant saves for a user and restrict them to their owner.

# Acceptance criteria

- The owner is the token `oid`, never a tool argument.
- Another user's artifact id answers 'artifact not found'.
- Artifacts are text only, at most 1 MiB per version and 50 documents per user. A document counts once, however many versions it has.
