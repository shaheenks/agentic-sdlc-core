---
type: Non-Functional Requirement
title: Tenant data stays out of the repository
description: Tenant, app, OAuth client, Entra group and user identifiers are never committed; Google group emails may be.
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
- No tenant ID, app ID, OAuth client ID or secret, Entra group ID, or test-user UPN or email appears in the repository.
- Google group email addresses may be committed in `config/` (they name the groups bound to roles).
- Bundle roots, which contain the tenant `users.yaml`, are kept out of git.

# Notes

Edited by CH-0011: `groups.yaml` no longer exists; bundles carry no group map.

Modified by [CH-0021](../../changes/CH-0021.md): per stack (Entra / GCP), design N7 to N10 and N13.
