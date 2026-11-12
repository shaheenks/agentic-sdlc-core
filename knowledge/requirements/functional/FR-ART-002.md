---
type: Functional Requirement
title: Artifact versions
description: A document keeps a stable id across versions and newer edits are never overwritten.
area: Artifacts
tags:
- requirement
- functional
- artifacts
status: draft
priority: should
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

The system shall keep versions of a document under one stable id and refuse a save that is not based on the latest version.

# Acceptance criteria

- `save_artifact(replaces=<id>, base_version=<n>)` adds the next version and is refused when `n` is not the latest.
- Stored rows are immutable and older versions stay readable by `version`.
- A document keeps at most 10 versions. Saving an 11th is refused and says to save it as a new document or delete it.

# Notes

Versions count against the per-document cap, not the per-user document limit (CH-0004, inventory gap 8 closed).
