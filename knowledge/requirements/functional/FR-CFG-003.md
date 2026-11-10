---
type: Functional Requirement
title: Immutable config bundles with rollback
description: Configuration is published as immutable versioned bundles, activated by a pointer and rolled back the same way.
area: Configuration
tags:
- requirement
- functional
- configuration
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:10:40+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
---

# Statement

The system shall publish configuration as immutable versioned bundles and switch or roll back the active version without rebuilding services.

# Acceptance criteria

- A bundle version is the git SHA plus a content hash.
- Activation and rollback move the `current` pointer; on GCP the MCP server polls it.
- Bundles contain no secrets.
