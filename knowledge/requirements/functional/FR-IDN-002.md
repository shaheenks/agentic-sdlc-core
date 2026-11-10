---
type: Functional Requirement
title: Membership from groups, app roles and direct members
description: A user's teams and roles come from Entra groups, Entra app roles and the per-environment direct-member list, combined as a union.
area: Identity
tags:
- requirement
- functional
- identity
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

The system shall derive a user's teams and roles from Entra group membership, Entra app roles and direct membership declared per environment, and combine them as a union.

# Acceptance criteria

- Group object IDs are mapped to aliases only in `config/env/<env>/groups.yaml`.
- App roles arrive in the token `roles` claim and each app-role persona resolves exactly like its group twin.
- Direct members (`users.yaml`) are matched on `oid` only; an entry without `oid` grants nothing.
- A token that omits groups (overage) yields no groups; app roles still apply.
