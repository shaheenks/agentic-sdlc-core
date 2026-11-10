---
type: Non-Functional Requirement
title: Repeatable data changes
description: Ingest and schema changes can be re-run safely.
area: Reliability
tags:
- requirement
- non-functional
- reliability
status: stable
priority: should
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:45:18+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
---

# Statement

Ingest runs and database setup shall be safe to repeat.

# Acceptance criteria

- Ingest skips unchanged content by hash.
- Migrations are append-only and checksummed.
- `sdlc-db bootstrap` is idempotent.
