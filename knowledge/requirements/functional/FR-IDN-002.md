---
type: Functional Requirement
title: Membership from app roles or groups and direct members
description: A user's teams and roles come from Entra app roles (Entra stack) or Google Groups (GCP stack) and the per-environment direct-member list, combined as a union.
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

The system shall derive a user's teams and roles from the stack's memberships (Entra app roles on the Entra stack, the configured Google Groups on the GCP stack) and direct membership declared per environment, and combine them as a union.

# Acceptance criteria

- App roles arrive in the token `roles` claim.
- Entra stack: direct members (`users.yaml`) are matched on `oid` only; an entry without `oid` grants nothing there.
- A `groups` claim is ignored if present: a token with groups but no app roles and no `users.yaml` entry gets only the signed-in basics.
- GCP stack: teams and roles are the union of the configured Google Groups the user belongs to (Cloud Identity Groups API) and `users.yaml` matched on the verified email; token claims for groups or roles are ignored there.
- A failed group lookup gives no group roles (fail closed).

# Notes

Edited by CH-0011: Entra groups and the group map are dropped (design D16).

Modified by [CH-0021](../../changes/CH-0021.md): per stack (Entra / GCP), design N7 to N10 and N13.
