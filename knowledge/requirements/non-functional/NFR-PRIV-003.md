---
type: Non-Functional Requirement
title: Tenant data stays out of the repository
description: Tenant, app, group and user identifiers are never committed.
area: Privacy
tags:
- requirement
- non-functional
- privacy
status: draft
priority: must
implementation: live
sources:
- id: rules
  resource: ../../rules/index.md
  title: Project rules (rule sets)
---

# Statement

Tenant-specific identifiers shall not be committed to the repository.

# Acceptance criteria

- `config/env/*/users.yaml` and `blocked.yaml` are git-ignored; only examples with placeholder GUIDs are committed.
- No tenant ID, app ID, group ID or test-user UPN appears in the repository.
- Bundle roots, which contain the tenant `users.yaml`, are kept out of git.

# Notes

Edited by CH-0011: `groups.yaml` no longer exists; bundles carry no group map.
