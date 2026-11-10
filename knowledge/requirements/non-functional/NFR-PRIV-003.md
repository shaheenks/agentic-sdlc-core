---
type: Non-Functional Requirement
title: Tenant data stays out of the repository
description: Tenant, app, group and user identifiers are never committed.
area: Privacy
tags:
- requirement
- non-functional
- privacy
status: stable
priority: must
implementation: live
verified:
- by: human:shaheenks
  at: '2026-11-10T21:30:44+05:30'
sources:
- id: rules
  resource: ../../../CLAUDE.md
  title: Project rules
---

# Statement

Tenant-specific identifiers shall not be committed to the repository.

# Acceptance criteria

- `config/env/*/groups.yaml`, `users.yaml` and `blocked.yaml` are git-ignored; only examples with placeholder GUIDs are committed.
- No tenant ID, app ID, group ID or test-user UPN appears in the repository.
- Bundle roots, which contain the tenant group map, are kept out of git.
