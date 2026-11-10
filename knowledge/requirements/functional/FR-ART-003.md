---
type: Functional Requirement
title: Download and review artifacts in the chat
description: Owners download artifacts and review them in the chat with line comments.
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

The system shall let owners download their artifacts and review them in the chat with comments on numbered lines.

# Acceptance criteria

- Downloads are served as attachments under the same token checks and the matching tool grant.
- `read_artifact(numbered=true)` numbers lines exactly as the chat's viewer does.
- Older versions are read-only in the viewer.
