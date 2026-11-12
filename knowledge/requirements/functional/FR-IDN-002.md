---
type: Functional Requirement
title: Membership from app roles and direct members
description: A user's teams and roles come from Entra groups, Entra app roles and the per-environment direct-member list, combined as a union.
area: Identity
tags:
- requirement
- functional
- identity
status: draft
priority: must
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

The system shall derive a user's teams and roles from Entra app roles and direct membership declared per environment, and combine them as a union.

# Acceptance criteria

- App roles arrive in the token `roles` claim.
- Direct members (`users.yaml`) are matched on `oid` only; an entry without `oid` grants nothing.
- A `groups` claim is ignored if present: a token with groups but no app roles and no `users.yaml` entry gets only the signed-in basics.

# Notes

Edited by CH-0011: Entra groups and the group map are dropped (design D16).
