---
type: Functional Requirement
title: Artifact versions
description: A document keeps a stable id across versions and newer edits are never overwritten.
area: Artifacts
tags:
- requirement
- functional
- artifacts
status: stable
priority: should
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:13:57+05:30'
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

# Notes

Open decision: how versions count against the 50-artifact limit (inventory gap 8).
