---
type: Non-Functional Requirement
title: Row-level security on all data
description: Postgres row-level security is the last line of defence for data access and no role can bypass it.
area: Security
tags:
- requirement
- non-functional
- security
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:30:44+05:30'
sources:
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
- id: inventory
  resource: ../../../docs/FEATURE_INVENTORY.md
  title: Feature inventory (baseline 2026-11-08)
---

# Statement

Every data table shall be protected by forced row-level security that no application role can bypass.

# Acceptance criteria

- Data tables have RLS enabled and forced, with policies for `sdlc_app` and `sdlc_ingest`.
- All reads go through `sdlc_db` with the allowed sources and maximum classification set for the session.
- `sdlc-db bootstrap` fails if any role can bypass RLS.
- Each data table has tests in `tests/db`.
