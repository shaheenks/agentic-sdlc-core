---
type: Functional Requirement
title: Explain and diff effective permissions
description: Operators can see what a persona may do and how a config change alters it.
area: Configuration
tags:
- requirement
- functional
- configuration
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

The system shall provide tooling to explain a persona's effective policy and to show per-persona permission changes between two configuration revisions.

# Acceptance criteria

- `sdlc-config explain` accepts a persona, a set of app roles, a set of Google group emails, or a direct-member alias, and resolves as either stack (`--stack`).
- `sdlc-config validate` fails when a persona resolves differently from its groups than from its app roles (stack parity).
- `sdlc-config diff` reports per-persona permission changes and runs on every config pull request.

# Notes

The diff covers permissions only, not team document-flow defaults (inventory gap 9).

Edited by CH-0011: groups are removed. A diff across the CH-0011 change itself cannot load the older config, which still names groups.

Modified by [CH-0021](../../changes/CH-0021.md): per stack (Entra / GCP), design N7 to N10 and N13.
